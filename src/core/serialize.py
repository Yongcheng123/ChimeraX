# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

"""
serialize: Support serialization of "simple" types
==================================================

Provide object serialization and deserialization for simple Python objects.
In this case, simple means numbers (int, float, numpy arrays), strings,
bytes, booleans, and non-recursive tuples, lists, sets, and dictionaries.
Recursive data-structures are not checked for and thus can cause an infinite
loop.  Arbitrary Python objects are not allowed.

Internally use pickle, with safeguards on what is written (so the author of
the code is more likely to find the bug before a user of the software does),
and on what is read.  The reading is more restrictive because the C-version
of the pickler will pickle objects, like arbtrary functions.  The
deserializer catches those mistakes, but later when the session is opened.

Version 1 of the protocol supports instances of the following types:

    :py:class:`bool`; :py:class:`int`; :py:class:`float`; :py:class:`complex`;
    numpy :py:class:`~numpy.ndarray`;
    :py:class:`str`; :py:class:`bytes`; :py:class:`bytearray`;
    type(:py:data:`None`);
    :py:class:`set`; :py:class:`frozenset`;
    :py:class:`dict`;
    :py:mod:`collections`' :py:class:`~collections.OrderedDict`,
    and :py:class:`~collections.deque`;
    :py:mod:`datetime`'s :py:class:`~datetime.datetime`,
    and :py:class:`~datetime.timedelta`;
    and :pillow:`PIL.Image.Image`.

"""
import msgpack
import pickle
import types  # for pickle support
# imports for supported "primitive" types and collections
# ** must be keep in sync with state.py **
import numpy
from collections import OrderedDict, deque
from datetime import datetime, timedelta
from PIL import Image
from .session import _UniqueName
from .state import FinalizedState

_PICKLE_PROTOCOL = 4


class _RestrictTable(dict):

    def __init__(self, *args, **kwds):
        dict.__init__(self, *args, **kwds)
        import copyreg
        if complex in copyreg.dispatch_table:
            self[complex] = copyreg.dispatch_table[complex]
        try:
            import numpy
            self[numpy.ndarray] = numpy.ndarray.__reduce__
        except ImportError:
            pass

    def get(self, cls, default=None):
        if isinstance(cls, types.BuiltinFunctionType):
            # need to allow for unpickling numpy arrays and other types
            return default
        if cls not in self:
            raise TypeError("Can not serialize class: %s" % cls.__name__)
        return dict.__getitem__(self, cls)


def pickle_serialize(stream, obj):
    """Put object in to a binary stream"""
    pickler = pickle.Pickler(stream, protocol=_PICKLE_PROTOCOL)
    pickler.fast = True     # no recursive lists/dicts/sets
    pickler.dispatch_table = _RestrictTable()
    pickler.dump(obj)


class _RestrictedUnpickler(pickle.Unpickler):

    supported = {
        'builtins': {'complex'},
        'collections': {'deque', 'Counter', 'OrderedDict'},
        'datetime': {'timedelta', 'datetime'},
        'numpy': {'ndarray', 'dtype'},
        'numpy.core.multiarray': {'_reconstruct', 'scalar'},
        'PIL.Image': {'Image'},
    }
    supported[_UniqueName.__module__] = {_UniqueName.__name__}
    supported[FinalizedState.__module__] = {FinalizedState.__name__}

    def find_class(self, module, name):
        if module in self.supported and name in self.supported[module]:
            return getattr(__import__(module, fromlist=(name,)), name)
        # Forbid everything else.
        fullname = '%s.%s' % (module, name)
        raise pickle.UnpicklingError("global '%s' is forbidden" % fullname)


def pickle_deserialize(stream):
    """Recover object from a binary stream"""
    unpickler = _RestrictedUnpickler(stream)
    return unpickler.load()

# msgpack can use 0-127 for msgpack extension types
# use some example handlers from u-msgpack-python
# TODO: look at msgpack_numpy for numpy ideas


def _encode_image(img):
    import io
    stream = io.BytesIO()
    img.save(stream, format='PNG')
    data = stream.getvalue()
    stream.close()
    return data


def _decode_image(data):
    import io
    stream = io.BytesIO(data)
    img = Image.open(stream)
    img.load()
    return img


def _encode_ndarray(o):
    # inspired by msgpack-numpy package
    if o.dtype.kind == 'V':
        # structured array
        kind = b'V'
        dtype = o.dtype.descr
    else:
        kind = b''
        dtype = o.dtype.str
    if 'O' in dtype:
        raise TypeError("Can not serialize numpy arrays of objects")
    return (
        (b'kind', kind), (b'dtype', dtype),
        (b'shape', o.shape), (b'data', o.tobytes())
    )


def _decode_ndarray(data):
    data = dict(data)
    kind = data[b'kind']
    dtype = data[b'dtype']
    if kind == b'V':
        dtype = [tuple(str(t) for t in d) for d in dtype]
    return numpy.fromstring(data[b'data'], numpy.dtype(dtype)).reshape(data[b'shape'])


def _encode_numpy_number(o):
    return (
        (b'dtype', o.dtype.str), (b'data', o.tobytes())
    )


def _decode_numpy_number(data):
    data = dict(data)
    return numpy.fromstring(data[b'data'], numpy.dtype(data[b'dtype']))[0]


def _decode_datetime(data):
    from dateutil.parser import parse
    return parse(data)


_encode_handlers = {
    # type : lambda returning OrderedDict with unique __type__ first
    # __type__ is index into decode array
    _UniqueName: lambda o: OrderedDict(
        (('__type__', 0), ('uid', o.uid))
    ),
    # __type__ == 1 is for numpy arrays
    complex: lambda o: OrderedDict(
        (('__type__', 2), ('args', (o.real, o.imag)))
    ),
    set: lambda o: OrderedDict(
        (('__type__', 3), ('args', tuple(o)))
    ),
    frozenset: lambda o: OrderedDict(
        (('__type__', 4), ('args', tuple(o)))
    ),
    OrderedDict: lambda o: OrderedDict(
        (('__type__', 5),) + tuple(o.items())
    ),
    deque: lambda o: OrderedDict(
        (('__type__', 6), ('args', tuple(o)))
    ),
    datetime: lambda o: OrderedDict(
        (('__type__', 7), ('arg', o.isoformat()))
    ),
    timedelta: lambda o: OrderedDict(
        (('__type__', 8), ('args', (o.days, o.seconds, o.microseconds)))
    ),
    Image.Image: lambda o: OrderedDict(
        (('__type__', 9), ('arg', _encode_image(o)))
    ),
    # __type__ == 10 is for numpy scalars
}


def _encode(obj):
    cvt = _encode_handlers.get(type(obj), None)
    if cvt is not None:
        return cvt(obj)
    # handle numpy subclasses
    if isinstance(obj, numpy.ndarray):
        return OrderedDict((('__type__', 1),) + _encode_ndarray(obj))
    if isinstance(obj, (numpy.number, numpy.bool_, numpy.bool8)):
        return OrderedDict((('__type__', 14),) + _encode_numpy_number(obj))

    raise RuntimeError("Can't convert object of type: %s" % type(obj))


_decode_handlers = [
    # order must match encode's __type__ values
    lambda args: _UniqueName(args[0][1]),
    _decode_ndarray,
    lambda args: complex(*args[0][1]),
    lambda args: set(args[0][1]),
    lambda args: frozenset(args[0][1]),
    OrderedDict,
    lambda args: deque(args[0][1]),
    lambda args: _decode_datetime(args[0][1]),
    lambda args: timedelta(*args[0][1]),
    lambda args: _decode_image(args[0][1]),
    lambda args: _decode_numpy_number(args),
]


def _decode_pairs(pairs):
    if not pairs:
        return dict()
    if pairs[0][0] != '__type__':
        return OrderedDict(pairs)
    cvt = _decode_handlers[pairs[0][1]]
    return cvt(pairs[1:])


def msgpack_serialize_stream(stream):
    packer = msgpack.Packer(default=_encode, use_bin_type=True,
                            use_single_float=False)
    return stream, packer


def msgpack_serialize(stream, obj):
    stream, packer = stream
    stream.write(packer.pack(obj))


def msgpack_deserialize_stream(stream):
    unpacker = msgpack.Unpacker(
        stream, object_pairs_hook=_decode_pairs, encoding='utf-8',
        use_list=False)
    return unpacker


def msgpack_deserialize(stream):
    try:
        return next(stream)
    except StopIteration:
        return None


if __name__ == '__main__':
    import io

    # serialize = pickle_serialize
    # deserialize = pickle_deserialize

    def serialize(buf, obj):
        packer = msgpack_serialize_stream(buf)
        msgpack_serialize(packer, obj)

    def deserialize(buf):
        unpacker = msgpack_deserialize_stream(buf)
        return msgpack_deserialize(unpacker)

    def test(obj, msg, expect_pass=True, idempotent=True):
        passed = 'pass' if expect_pass else 'fail'
        failed = 'fail' if expect_pass else 'pass'
        with io.BytesIO() as buf:
            try:
                serialize(buf, obj)
                buf.seek(0)
                result = deserialize(buf)
                if isinstance(obj, numpy.ndarray):
                    assert(numpy.array_equal(result, obj))
                else:
                    assert(result == obj)
            except AssertionError:
                if idempotent:
                    print('%s: %s: not idempotent' % (failed, msg))
                else:
                    print('%s: %s' % (passed, msg))
            except TypeError as e:
                if failed == "fail":
                    print('%s (early): %s: %s' % (failed, msg, e))
                else:
                    print('%s (early): %s' % (failed, msg))
            except Exception as e:
                if failed == "fail":
                    print('%s: %s: %s' % (failed, msg, e))
                else:
                    print('%s: %s' % (failed, msg))
            else:
                print('%s: %s' % (passed, msg))

    # test: basic type support
    test(3, 'an int')
    test(42.0, 'a float')
    test('chimera', 'a string')
    test(complex(3, 4), 'a complex')
    test(False, 'False')
    test(True, 'True')
    test(None, 'None')
    test(b'xyzzy', 'some bytes')
    test(((0, 1), (2, 0)), 'nested lists')
    test({'a': {0: 1}, 'b': {2: 0}}, 'nested dicts')
    test({1, 2, frozenset([3, 4])}, 'frozenset nested in a set')
    test(bool, 'can not serialize bool', expect_pass=False)
    test(float, 'can not serialize float', expect_pass=False)
    test(int, 'can not serialize int', expect_pass=False)
    test(set, 'can not serialize set', expect_pass=False)

    # test: objects
    class C:
        pass
    test_obj = C()
    test_obj.test = 12
    test(C, 'can not serialize class definition', expect_pass=False)
    test(test_obj, 'can not serialize objects', expect_pass=False)

    # test: functions
    test(serialize, 'can not serialize function objects', expect_pass=False)
    test(abs, 'can not serialize builtin functions', expect_pass=False)

    # test: numpy arrays
    test_obj = numpy.zeros((2, 2), dtype=numpy.float32)
    test(test_obj, 'numerical numpy array')
    test_obj = numpy.empty((2, 2), dtype=numpy.float32)
    test(test_obj, 'empty numerical numpy array')

    class C:
        pass
    test_obj = numpy.empty((2, 2), dtype=object)
    test_obj[:, :] = C()
    test(test_obj, 'can not serialize numpy array of objects',
         expect_pass=False)

    import sys
    if sys.platform.startswith('win'):
        with open("nul:") as f:
            test(f, 'can not serialize file object', expect_pass=False)
    else:
        with open("/bin/ls") as f:
            test(f, 'can not serialize file object', expect_pass=False)

    # d = date(2000, 1, 1)
    # test(d, 'date')
    # t = time()
    # test(t, 'time')
    t = timedelta()
    test(t, 'timedelta')
    d = datetime.now()
    test(d, 'datetime')
    d = datetime.now().astimezone()
    test(d, 'datetime&timezone')
    from datetime import timezone
    d = datetime.now(timezone.utc)
    test(d, 'datetime&utc timezone')

    import enum

    class Color(enum.Enum):
        red = 1
    c = Color.red
    test(c, 'can not serialize Enum subclass', expect_pass=False)

    # this fails with pickle, but works with msgpack
    class Color(enum.IntEnum):
        red = 1
    c = Color.red
    test(c, 'IntEnum subclass instance')

    d = OrderedDict([(1, 2), (3, 4)])
    test(d, 'ordered dict')

    from PIL import Image
    test(Image.new("RGB", (32, 32), "white"), 'PIL image', idempotent=False)
