# coding: utf-8

"""
    RBVI ChimeraX Web Services

    REST API for RBVI web services supporting ChimeraX tools  # noqa: E501

    OpenAPI spec version: 0.1
    Contact: chimerax-users@cgl.ucsf.edu
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

from setuptools import setup, find_packages  # noqa: H301

NAME = "cxservices"
VERSION = "1.0"
# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = ["urllib3 >= 1.15", "six >= 1.10", "certifi", "python-dateutil"]

setup(
    name=NAME,
    version=VERSION,
    description="RBVI ChimeraX Web Services",
    author_email="chimerax-users@cgl.ucsf.edu",
    url="",
    keywords=["Swagger", "RBVI ChimeraX Web Services"],
    install_requires=REQUIRES,
    packages=find_packages(exclude=["test"]),
    include_package_data=True,
    long_description="""\
    REST API for RBVI web services supporting ChimeraX tools  # noqa: E501
    """
)