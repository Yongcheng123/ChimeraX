_GapChars = "-. "

class Blast_Output_Parser:
  """Parser for XML output from blastp (tested against version 2.2.29+)."""

  def __init__(self, name, xmlText):

    self.name = name

    # Bookkeeping data
    self.matches = []

    # Data from results
    self.database = None
    self.query = None
    self.queryLength = None
    self.reference = None
    self.version = None

    self.gapExistence = None
    self.gapExtension = None
    self.matrix = None

    self.dbSizeSequences = None
    self.dbSizeLetters = None

    # Extract information from results
    import xml.etree.ElementTree as ET
    tree = ET.fromstring(xmlText)
    if tree.tag != "BlastOutput":
      raise ValueError("Text is not BLAST XML output")
    self._extractRoot(tree)
    e = tree.find("./BlastOutput_param/Parameters")
    if e is not None:
      self._extractParams(e)
    el = tree.findall("BlastOutput_iterations/Iteration")
    if len(el) > 1:
      raise ValueError("Multi-iteration BLAST output unsupported")
    elif len(el) == 0:
      raise ValueError("No iteration data in BLAST OUTPUT")
    iteration = el[0]
    for he in iteration.findall("./Iteration_hits/Hit"):
      self._extractHit(he)
    self._extractStats(iteration.find("./Iteration_stat/Statistics"))

  def _text(self, parent, tag):
    e = parent.find(tag)
    return e is not None and e.text.strip() or None

  def _extractRoot(self, oe):
    self.database = self._text(oe, "BlastOutput_db")
    self.query = self._text(oe, "BlastOutput_query-ID")
    self.queryLength = int(self._text(oe, "BlastOutput_query-len"))
    self.reference = self._text(oe, "BlastOutput_reference")
    self.version = self._text(oe, "BlastOutput_version")

  def _extractParams(self, pe):
    self.gapExistence = self._text(pe, "Parameters_gap-open")
    self.gapExtension = self._text(pe, "Parameters_gap-extend")
    self.matrix = self._text(pe, "Parameters_matrix")

  def _extractStats(self, se):
    self.dbSizeSequences = self._text(se, "Statistics_db-num")
    self.dbSizeLetters = self._text(se, "Statistics_db-len")

  def _extractHit(self, he):
    hid = self._text(he, "Hit_id")
    hdef = self._text(he, "Hit_def")
#    desc = '>%s %s' % (hid, hdef)
    desc = hdef
    for hspe in he.findall("./Hit_hsps/Hsp"):
      self._extractHSP(hspe, desc)

  def _extractHSP(self, hspe, desc):
    score = int(float(self._text(hspe, "Hsp_bit-score"))) #SH
    evalue = float(self._text(hspe, "Hsp_evalue"))
    qSeq = self._text(hspe, "Hsp_qseq")
    qStart = int(self._text(hspe, "Hsp_query-from"))
    qEnd = int(self._text(hspe, "Hsp_query-to"))
    hSeq = self._text(hspe, "Hsp_hseq")
    hStart = int(self._text(hspe, "Hsp_hit-from"))
    hEnd = int(self._text(hspe, "Hsp_hit-to"))
    m = Match(desc, score, evalue, qStart, qEnd, qSeq, hStart, hEnd, hSeq) #SH
    self.matches.append(m)

class Match:
  """Data from a single BLAST hit."""

  def __init__(self, desc, score, evalue, qStart, qEnd, qSeq, hStart, hEnd, hSeq): #SH
    self.description = desc
    self.score = score
    self.evalue = evalue
    self.qStart = qStart - 1        # switch to 0-base indexing
    self.qEnd = qEnd - 1
    self.qSeq = qSeq
    self.hStart = hStart - 1        # switch to 0-base indexing
    self.hEnd = hEnd - 1
    self.hSeq = hSeq
    if len(qSeq) != len(hSeq):
      raise ValueError("sequence alignment length mismatch")

  def __repr__(self):
    return "<Match %s>" % (self.name(),)

  def name(self):
    return ' '.join('%s %s' % (id, ','.join(c)) for id,c,desc in self.pdb_chains())

  def pdb_chains(self):
    '''Return PDB chains for this match as a list of 3-tuples,
    containing pdb id, list of chain ids, and pdb description.'''

    pdbs = {}
    for pc in self.description.split('|'):
      pdb_id, chains, desc = pc.split(maxsplit = 2)
      cids = chains.split(',')
      pdbs[pdb_id] = (cids,desc)

    pcd = [(pdb_id,c,desc) for pdb_id,(c,desc) in pdbs.items()]
    pcd.sort()
    return pcd

  def load_structures(self, session):
    mols = []
    from . import mmcif
    from .opensave import open_data
    for pdb_id,chains,desc in self.pdb_chains():
      m = open_data(pdb_id, session, from_database = 'PDBmmCIF', history = False)[0]
      if m:
        m.blast_match = self
        m.blast_match_chains = chains
        m.blast_match_description = desc
        mols.append(m)
    return mols

  def residue_number_pairing(self):
    '''
    Returns two arrays of matching hit and query residue numbers.
    Sequence position 1 is residue number 1.
    '''
    if hasattr(self, 'rnum_pairs'):
      return self.rnum_pairs
    hs, qs = self.hSeq, self.qSeq
    h, q = self.hStart+1, self.qStart+1
    n = min(len(hs), len(qs))
    from numpy import empty, int32
    hp,qp = empty((n,), int32), empty((n,), int32)
    p = 0
    for i in range(n):
      hstep = 0 if hs[i] in _GapChars else 1
      qstep = 0 if qs[i] in _GapChars else 1
      if hstep and qstep:
        hp[p] = h
        qp[p] = q
        p += 1
      h += hstep
      q += qstep
    from numpy import resize
    self.rnum_pairs = hqp = resize(hp, (p,)), resize(qp, (p,))
    return hqp

  def identical_residue_count(self):
    if not hasattr(self, 'nequal'):
      from numpy import frombuffer, byte
      self.nequal = sum(frombuffer(self.hSeq.encode('utf-8'), byte) == frombuffer(self.qSeq.encode('utf-8'), byte))
    return self.nequal

def check_hit_sequences_match_mmcif_sequences(mols):

  for m in mols:
    ma = m.blast_match
    chains = m.blast_match_chains

    # Compute gapless hit sequence from match
    hseq = ma.hSeq
    for c in _GapChars:
      hseq = hseq.replace(c,'')
    hseq = '.'*ma.hStart + hseq

    # Using mmcif files the residue number (label_seq_id) is the index into the sequence.
    # This is not true of PDB files.
    from ..molecule.molecule import chain_sequence
    for cid in chains:
      cseq = chain_sequence(m, cid)
      # Check that hit sequence matches PDB sequence
      if not sequences_match(hseq,cseq):
        print ('%s %s\n%s\n%s' % (m.name, cid, cseq, hseq))

def match_metrics_table(molecule, chain, mols):
  nqres = len(molecule.sequence)
  qrmask = molecule.residue_number_mask(chain, nqres)
  lines = [' PDB Chain  RMSD  Coverage(#,%) Identity(#,%) Score  Description']
  for m in mols:
    ma = m.blast_match
    chains = m.blast_match_chains
    hrnum, qrnum = ma.residue_number_pairing()      # Hit and query residue number pairing
    npair = len(hrnum)
    neq = ma.identical_residue_count()

    m.blast_match_residue_numbers = hrnum
    m.blast_match_rmsds = rmsds = {}

    for cid in chains:

      # Find paired hit and query residues having CA atoms for doing an alignment.
      hrmask = m.residue_number_mask(cid, hrnum.max())
      from numpy import logical_and
      p = logical_and(hrmask[hrnum],qrmask[qrnum]).nonzero()[0]
      hpatoms = m.atom_subset('CA', cid, residue_numbers = hrnum[p])
      qpatoms = molecule.atom_subset('CA', chain, residue_numbers = qrnum[p])

      # Compute RMSD of aligned hit and query.
      from ..molecule import align
      tf, rmsd = align.align_points(hpatoms.coordinates(), qpatoms.coordinates())
      rmsds[cid] = rmsd

      # Align hit chain to query chain
      m.atom_subset(chain_id = cid).move_atoms(tf)

      # Create table output line showing how well hit matches query.
      name = m.name[:-4] if m.name.endswith('.cif') else m.name
      desc = m.blast_match_description if cid == chains[0] else ''
      lines.append('%4s %3s %7.2f %5d %5.0f   %5d %5.0f  %5d    %s'
                   % (name, cid, rmsd, npair, 100*npair/nqres,
                      neq, 100.0*neq/npair, ma.score, desc))

  return '\n'.join(lines)

def show_matches_as_ribbons(qmol, chain, mols, rescolor = (225,130,130,255)):
  for m in mols:
    m.single_color()
    for cid in m.blast_match_chains:
      r = m.atom_subset(chain_id = cid, residue_numbers = m.blast_match_residue_numbers)
      r.color_ribbon(rescolor)
    show_only_ribbons(m, m.blast_match_chains)
    m.set_ribbon_radius(0.25)
  qmol.set_ribbon_radius(0.25)
  show_only_ribbons(qmol, [chain])

def show_only_ribbons(m, chains):
    m.atoms().hide_atoms()
    m.atom_subset(chain_id = chains).show_ribbon(only_these = True)

def color_by_coverage(matches, mol, chain,
                      c0 = (200,200,200,255), c100 = (0,255,0,255)):
  rmax = max(ma.qEnd for ma in matches) + 1     # qEnd uses zero-base indexing, need 1-base
  from numpy import zeros, float32, outer, uint8
  qrc = zeros((rmax+1,), float32)
  for ma in matches:
    hrnum, qrnum = ma.residue_number_pairing()
    qrc[qrnum] += 1

  qrc /= len(matches)
  rcolors = (outer((1-qrc),c0) + outer(qrc,c100)).astype(uint8)
  mol.color_ribbon(chain, rcolors)
  return qrc[1:].min(), qrc[1:].max()

def blast_color_by_coverage(session):
  if not hasattr(session, 'blast_results'):
    return 
  mol, chain, results, mols = session.blast_results
  for m in mols:
    m.display = False
  cmin, cmax = color_by_coverage(results.matches, mol, chain)
  session.show_status('Residues colored by number of sequence hits (%.0f-%.0f%%)' % (100*cmin, 100*cmax))

def show_only_matched_residues(mols):
  for m in mols:
    ma = m.blast_match
    hrnum, qrnum = ma.residue_number_pairing()
    m.atom_subset(chain_id = m.blast_match_chains, residue_numbers = hrnum).show_ribbon(only_these = True)
    m.display = True

def blast_show_matched_residues(session):
  if not hasattr(session, 'blast_results'):
    return 
  mol, chain, results, mols = session.blast_results
  show_only_matched_residues(mols)

def sequences_match(s, seq):
  n = min(len(s), len(seq))
  for i in range(n):
    if s[i] != seq[i] and s[i] != '.' and s[i] != 'X' and seq[i] != '.' and seq[i] != 'X':
      return False
  return True

def divide_string(s, prefix):
  ds = []
  i = 0
  while True:
    e = s.find(prefix,i+1)
    if e == -1:
      ds.append(s[i:])
      break
    ds.append(s[i:e])
    i = e
  return ds

def create_fasta_database(mmcif_dir):
  '''Create fasta file for blast database using mmcif divided database sequences.
  Make just one entry for identical sequences that come from multiple pdbs or chains.'''
  seq_ids = {}
  from os import path, listdir
  from . import mmcif
  for dir2 in listdir(mmcif_dir):
    d2 = path.join(mmcif_dir,dir2)
    if path.isdir(d2):
      print(dir2)
      for ciffile in listdir(d2):
        if ciffile.endswith('.cif'):
          cifpath = path.join(d2, ciffile)
          cseq = mmcif.mmcif_sequences(cifpath)
          pdb_id = ciffile[:4]
          for cid, (start,seq,desc) in cseq.items():
            pt = seq_ids.setdefault(seq,{})
            if pdb_id in pt:
              pt[pdb_id][0].append(cid)
            else:
              pt[pdb_id] = ([cid],desc)
  lines = []
  for seq, ids in seq_ids.items():
    lines.append('>%s' % '|'.join('%s %s %s' % (id, ','.join(sorted(cids)), desc) for id,(cids,desc) in ids.items()))
    lines.append(seq)
  fa = '\n'.join(lines)
  return fa

def write_fasta(name, seq, file):
  file.write('>%s\n%s\n' % (name, seq))

def run_blastp(name, fasta_path, output_path, blast_program, blast_database):
  # ../bin/blastp -db pdbaa -query 2v5z.fasta -outfmt 5 -out test.xml
  from os.path import dirname, basename
  dbdir, dbname = dirname(blast_database), basename(blast_database)
  cmd = ('env BLASTDB=%s %s -db %s -query %s -outfmt 5 -out %s' %
         (dbdir, blast_program, dbname, fasta_path, output_path))
  print (cmd)
  import os
  os.system(cmd)
  f = open(output_path)
  xml_text = f.read()
  f.close()
  results = Blast_Output_Parser(name, xml_text)
  return results

def blast_command(cmdname, args, session):

  from ..ui.commands import molecule_arg, string_arg, parse_arguments
  req_args = (('molecule', molecule_arg),
              ('chain', string_arg),)
  opt_args = ()
  kw_args = (('blastProgram', string_arg),
             ('blastDatabase', string_arg),)

  kw = parse_arguments(cmdname, args, session, req_args, opt_args, kw_args)
  kw['session'] = session
  blast(**kw)

def blast(molecule, chain, session,
          blastProgram = '/usr/local/ncbi/blast/bin/blastp',
          blastDatabase = '/usr/local/ncbi/blast/db/mmcif'):

  # Write FASTA sequence file for molecule
  session.show_status('Blast %s chain %s, running...' % (molecule.name, chain))
  from . import mmcif
  s = mmcif.mmcif_sequences(molecule.path)
  start,seq,desc = s[chain]
  molecule.sequence = seq
  from os.path import basename, splitext
  prefix = splitext(basename(molecule.path))[0]
  import tempfile
  fasta_file = tempfile.NamedTemporaryFile('w', suffix = '.fasta', prefix = prefix+'_', delete = False)
  sname = '%s %s' % (prefix, chain)
  write_fasta(sname, seq, fasta_file)
  fasta_file.close()

  # Run blastp standalone program and parse results
  blast_output = splitext(fasta_file.name)[0] + '.xml'
  results = run_blastp(molecule.name, fasta_file.name, blast_output, blastProgram, blastDatabase)
  matches = results.matches

  # Report number of matches
  np = sum(len(m.pdb_chains()) for m in matches)
  nc = sum(sum(len(c) for id,c,desc in m.pdb_chains()) for m in matches)
  msg = ('%s chain %s, sequence length %d\nsequence %s\n%d sequence matches, %d PDBs, %d chains'
         % (molecule.name, chain, len(seq), seq, len(matches), np, nc))
  session.show_info(msg)

  # Load matching structures
  session.show_status('Blast %s chain %s, loading %d sequence hits'
                      % (molecule.name, chain, len(results.matches)))
  mols = sum([m.load_structures(session) for m in results.matches], [])
  session.add_models(mols)

  # Report match metrics, align hit structures and show ribbons
  session.show_status('Blast %s chain %s, computing RMSDs...' % (molecule.name, chain))
  session.show_info(match_metrics_table(molecule, chain, mols))
  session.show_status('Blast %s chain %s, show hits as ribbons...' % (molecule.name, chain))
  show_matches_as_ribbons(molecule, chain, mols)
  session.show_status('Blast %s chain %s, done...' % (molecule.name, chain))

  # Preserve most recent blast results for use by keyboard shortcuts
  session.blast_results = (molecule, chain, results, mols)

def cycle_blast_molecule_display(session):
  cycler(session).toggle_play()
def next_blast_molecule_display(session):
  cycler(session).show_next()
def previous_blast_molecule_display(session):
  cycler(session).show_previous()
def all_blast_molecule_display(session):
  cycler(session).show_all()

def cycler(session):
  if not hasattr(session, 'blast_cycler'):
    session.blast_cycler = Blast_Display_Cycler(session)
  return session.blast_cycler

class Blast_Display_Cycler:
  def __init__(self, session):
    self.frame = None
    self.frames_per_molecule = 10
    self.session = session
    self.results_id = None
    self.hchains = None
    self.last_mol = None
    self.hit_num = 0
  def toggle_play(self):
    if self.frame is None:
      self.frame = 0
      self.show_none()
      v = self.session.view
      v.add_new_frame_callback(self.next_frame)
    else:
      self.stop_play()
      self.show_all()
  def stop_play(self):
    if self.frame is None:
      return
    self.frame = None
    v = self.session.view
    v.remove_new_frame_callback(self.next_frame)
  def hit_molecules(self):
    return self.session.blast_results[3]
  def hit_chains(self):
    if self.hchains is None or id(self.session.blast_results) != self.results_id:
      self.hchains = sum([[(m,c) for c in m.blast_match_chains] for m in self.hit_molecules()], [])
      self.results_id = id(self.session.blast_results)
    return self.hchains
  def show_next(self):
    self.stop_play()
    self.show_hit((self.hit_num + 1) % len(self.hit_chains()))
  def show_previous(self):
    self.stop_play()
    nh = len(self.hit_chains())
    self.show_hit((self.hit_num + nh - 1) % nh)
  def show_all(self):
    self.stop_play()
    for m in self.hit_molecules():
      m.display = True
      show_only_ribbons(m, m.blast_match_chains)
    self.last_mol = None
  def show_none(self):
    for m in self.hit_molecules():
      m.display = False
    self.last_mol = None
  def show_hit(self, hnum):
    self.hit_num = hnum
    hc = self.hit_chains()
    m,c = hc[hnum]
    lm = self.last_mol
    if not m is lm:
      if lm:
        lm.display = False
      else:
        self.show_none()
      m.display = True
      self.last_mol = m
    show_only_ribbons(m,[c])
    s = self.session
    s.show_status('%s %s   rmsd %.2f   %s' %
                  (m.name, c, m.blast_match_rmsds[c], m.blast_match_description))
  def next_frame(self):
    f = self.frame
    if f == 0:
      self.show_hit(self.hit_num)
    if f+1 >= self.frames_per_molecule:
      self.frame = 0
      self.hit_num = (self.hit_num + 1) % len(self.hit_chains())
    else:
      self.frame += 1

