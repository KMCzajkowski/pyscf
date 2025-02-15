from __future__ import print_function, division
import numpy as np
import sys

from pyscf.nao.m_color import color as bc
from pyscf.nao.m_system_vars_dos import system_vars_dos, system_vars_pdos
from pyscf.nao.m_siesta2blanko_csr import _siesta2blanko_csr
from pyscf.nao.m_siesta2blanko_denvec import _siesta2blanko_denvec
from pyscf.nao.m_siesta_ion_add_sp2 import _siesta_ion_add_sp2
from pyscf.nao.m_ao_log import ao_log_c

#
#
#
def get_orb2m(sv):
  orb2m = np.empty(sv.norbs, dtype='int64')
  orb = 0
  for atom,sp in enumerate(sv.atom2sp):
    for mu,j in enumerate(sv.sp_mu2j[sp]):
      for m in range(-j,j+1): orb2m[orb],orb = m,orb+1
  return orb2m

#
#
#
def get_orb2j(sv):
  orb2j = np.empty(sv.norbs, dtype='int64')
  orb = 0
  for atom,sp in enumerate(sv.atom2sp):
    for mu,j in enumerate(sv.sp_mu2j[sp]):
      for m in range(-j,j+1): orb2j[orb],orb = j,orb+1
  return orb2j

#
#
#
def diag_check(sv, atol=1e-5, rtol=1e-4):
  from pyscf.nao.m_sv_diag import sv_diag 
  ksn2e = sv.xml_dict['ksn2e']
  ac = True
  for k,kvec in enumerate(sv.xml_dict["k2xyzw"]):
    for spin in range(sv.nspin):
      e,x = sv_diag(sv, kvec=kvec[0:3], spin=spin)
      eref = ksn2e[k,spin,:]
      acks = np.allclose(eref,e,atol=atol,rtol=rtol)
      ac = ac and acks
      if(not acks):
        aerr = sum(abs(eref-e))/len(e)
        print("diag_check: "+bc.RED+str(k)+' '+str(spin)+' '+str(aerr)+bc.ENDC)
  return ac

#
#
#
def overlap_check(sv, tol=1e-5, **kvargs):
  over = sv.overlap_coo(**kvargs).tocsr()
  diff = (sv.hsx.s4_csr-over).sum()
  summ = (sv.hsx.s4_csr+over).sum()
  ac = diff/summ<tol
  if not ac: print(diff, summ)
  return ac

#
#
#
class system_vars_c():

  def __init__(self):
    """ 
      Constructor of system_vars class: so far can be initialized 
      with SIESTA orbitals and Hamiltonian and wavefunctions
    """
    self.state = 'call an initialize method...'

  #
  #
  #
  def init_xyzlike(self, atom, label='pyscf'):
    """ This is simple constructor which only initializes geometry info """
    from pyscf.lib import logger
    from pyscf.data import chemical_symbols
    self.verbose = logger.NOTE  # To be similar to Mole object...
    self.stdout = sys.stdout
    self.symmetry = False
    self.symmetry_subgroup = None

    self.label = label
    atom2charge = [atm[0] for atm in atom]
    self.atom2coord = np.array([atm[1] for atm in atom])
    self.sp2charge = list(set(atom2charge))
    self.sp2symbol = [chemical_symbols[z] for z in self.sp2charge]
    self.atom2sp = [self.sp2charge.index(charge) for charge in atom2charge]
    self.natm=self.natoms=len(self.atom2sp)
    self.atom2s = None
    self.nspin = 1
    self.state = 'should be useful for something'
    return self

  #
  #
  #
  def init_pyscf_gto(self, gto, label='pyscf', **kvargs):
    """Interpret previous pySCF calculation"""
    from pyscf.lib import logger

    self.verbose = logger.NOTE  # To be similar to Mole object...
    self.stdout = sys.stdout
    self.symmetry = False
    self.symmetry_subgroup = None

    self.label = label
    self.mol=gto # Only some data must be copied, not the whole object. Otherwise, an eventual deepcopy(...) may fail.
    self.natm=self.natoms = gto.natm
    a2s = [gto.atom_symbol(ia) for ia in range(gto.natm) ]
    self.sp2symbol = sorted(list(set(a2s)))
    self.nspecies = len(self.sp2symbol)
    self.atom2sp = np.empty((gto.natm), dtype='int64')
    for ia,sym in enumerate(a2s): self.atom2sp[ia] = self.sp2symbol.index(sym)

    self.sp2charge = [-999]*self.nspecies
    for ia,sp in enumerate(self.atom2sp): self.sp2charge[sp]=gto.atom_charge(ia)
    self.ao_log = ao_log_c().init_ao_log_gto_suggest_mesh(gto, self, **kvargs)
    self.atom2coord = np.zeros((self.natm, 3))
    for ia,coord in enumerate(gto.atom_coords()): self.atom2coord[ia,:]=coord # must be in Bohr already?
    self.atom2s = np.zeros((self.natm+1), dtype=np.int64)
    for atom,sp in enumerate(self.atom2sp): self.atom2s[atom+1]=self.atom2s[atom]+self.ao_log.sp2norbs[sp]
    self.norbs = self.norbs_sc = self.atom2s[-1]
    self.nspin = 1
    self.ucell = 20.0*np.eye(3)
    self.atom2mu_s = np.zeros((self.natm+1), dtype=np.int64)
    for atom,sp in enumerate(self.atom2sp): self.atom2mu_s[atom+1]=self.atom2mu_s[atom]+self.ao_log.sp2nmult[sp]
    self._atom = gto._atom
    self.basis = gto.basis
    self.init_libnao()
    self.state = 'should be useful for something'
    return self
    

  #
  #
  #
  def init_ase_atoms(self, Atoms, **kvargs):
    """ Initialise system vars using siesta file and Atom object from ASE."""
    from pyscf.nao.m_siesta_xml import siesta_xml
    from pyscf.nao.m_siesta_wfsx import siesta_wfsx_c
    from pyscf.nao.m_siesta_ion_xml import siesta_ion_xml
    from pyscf.nao.m_siesta_hsx import siesta_hsx_c

    self.label = 'ase' if label is None else label
    self.xml_dict = siesta_xml(self.label)
    self.wfsx = siesta_wfsx_c(self.label)
    self.hsx = siesta_hsx_c(self.label, **kvargs)
    self.norbs_sc = self.wfsx.norbs if self.hsx.orb_sc2orb_uc is None else len(self.hsx.orb_sc2orb_uc)

    try:
      import ase
    except:
      warn('no ASE installed: try via siesta.xml')
      self.init_siesta_xml(**kvargs)

    self.Atoms = Atoms
   
    ##### The parameters as fields     
    self.sp2ion = []
    species = []
    for sp in Atoms.get_chemical_symbols():
      if sp not in species:
        species.append(sp)
        self.sp2ion.append(siesta_ion_xml(sp+'.ion.xml'))
    
    _add_mu_sp2(self, self.sp2ion)
    self.sp2ao_log = ao_log_c(self.sp2ion)
  
    self.natm=self.natoms= Atoms.get_positions().shape[0]
    self.norbs  = self.wfsx.norbs
    self.nspin  = self.wfsx.nspin
    self.nkpoints  = self.wfsx.nkpoints

    strspecie2sp = {}
    for sp in range(len(self.wfsx.sp2strspecie)): strspecie2sp[self.wfsx.sp2strspecie[sp]] = sp
    
    self.atom2sp = np.empty((self.natoms), dtype='int64')
    for i, sp in enumerate(Atoms.get_chemical_symbols()):
      self.atom2sp[i] = strspecie2sp[sp]
    
    self.atom2s = np.zeros((sv.natm+1), dtype=np.int64)
    for atom,sp in enumerate(sv.atom2sp): atom2s[atom+1]=atom2s[atom]+self.ao_log.sp2norbs[sp]

    self.atom2mu_s = np.zeros((self.natm+1), dtype=np.int64)
    for atom,sp in enumerate(self.atom2sp): self.atom2mu_s[atom+1]=self.atom2mu_s[atom]+self.ao_log.sp2nmult[sp]

    orb2m = get_orb2m(self)
    _siesta2blanko_csr(orb2m, self.hsx.s4_csr, self.hsx.orb_sc2orb_uc)

    for s in range(self.nspin):
      _siesta2blanko_csr(orb2m, self.hsx.spin2h4_csr[s], self.hsx.orb_sc2orb_uc)
    
    for k in range(self.nkpoints):
      for s in range(self.nspin):
        for n in range(self.norbs):
          _siesta2blanko_denvec(orb2m, self.wfsx.X[k,s,n,:,:])

    self.sp2symbol = [str(ion['symbol'].replace(' ', '')) for ion in self.sp2ion]
    self.sp2charge = self.ao_log.sp2charge
    self.state = 'should be useful for something'
    return self

  #
  #
  #
  def init_siesta_xml(self, label='siesta', cd='.', **kvargs):
    from pyscf.nao.m_siesta_xml import siesta_xml
    from pyscf.nao.m_siesta_wfsx import siesta_wfsx_c
    from pyscf.nao.m_siesta_ion_xml import siesta_ion_xml
    from pyscf.nao.m_siesta_hsx import siesta_hsx_c
    from timeit import default_timer as timer
    """
      Initialise system var using only the siesta files (siesta.xml in particular is needed)

      System variables:
      -----------------
        label (string): calculation label
        chdir (string): calculation directory
        xml_dict (dict): information extracted from the xml siesta output, see m_siesta_xml
        wfsx: class use to extract the information about wavefunctions, see m_siesta_wfsx
        hsx: class to store a sparse representation of hamiltonian and overlap, see m_siesta_hsx
        norbs_sc (integer): number of orbital
        ucell (array, float): unit cell
        sp2ion (list): species to ions, list of the species associated to the information from the ion files, see m_siesta_ion_xml
        ao_log: Atomic orbital on an logarithmic grid, see m_ao_log
        atom2coord (array, float): array containing the coordinates of each atom.
        natm, natoms (integer): number of atoms
        norbs (integer): number of orbitals
        nspin (integer): number of spin
        nkpoints (integer): number of kpoints
        fermi_energy (float): Fermi energy
        atom2sp (list): atom to specie, list associating the atoms to their specie number
        atom2s: atom -> first atomic orbital in a global orbital counting
        atom2mu_s: atom -> first multiplett (radial orbital) in a global counting of radial orbitals
        sp2symbol (list): list soociating the species to them symbol
        sp2charge (list): list associating the species to them charge
        state (string): this is an internal information on the current status of the class
    """

    self.label = label
    self.cd = cd
    self.xml_dict = siesta_xml(cd+'/'+self.label+'.xml')
    self.wfsx = siesta_wfsx_c(label, cd, **kvargs)
    self.hsx = siesta_hsx_c(cd+'/'+self.label+'.HSX', **kvargs)
    self.norbs_sc = self.wfsx.norbs if self.hsx.orb_sc2orb_uc is None else len(self.hsx.orb_sc2orb_uc)
    self.ucell = self.xml_dict["ucell"]
    ##### The parameters as fields     
    self.sp2ion = []
    for sp in self.wfsx.sp2strspecie: self.sp2ion.append(siesta_ion_xml(cd+'/'+sp+'.ion.xml'))

    _siesta_ion_add_sp2(self, self.sp2ion)
    self.ao_log = ao_log_c().init_ao_log_ion(self.sp2ion)

    self.atom2coord = self.xml_dict['atom2coord']
    self.natm=self.natoms=len(self.xml_dict['atom2sp'])
    self.norbs  = self.wfsx.norbs 
    self.nspin  = self.wfsx.nspin
    self.nkpoints  = self.wfsx.nkpoints
    self.fermi_energy = self.xml_dict['fermi_energy']

    strspecie2sp = {}
    # initialise a dictionary with species string as key
    # associated to the specie number
    for sp,strsp in enumerate(self.wfsx.sp2strspecie): strspecie2sp[strsp] = sp
    
    # list of atoms associated to them specie number
    self.atom2sp = np.empty((self.natm), dtype=np.int64)
    for o,atom in enumerate(self.wfsx.orb2atm):
      self.atom2sp[atom-1] = strspecie2sp[self.wfsx.orb2strspecie[o]]

    self.atom2s = np.zeros((self.natm+1), dtype=np.int64)
    for atom,sp in enumerate(self.atom2sp):
        self.atom2s[atom+1]=self.atom2s[atom]+self.ao_log.sp2norbs[sp]

    # atom2mu_s list of atom associated to them mu number (defenition of mu??)
    # mu number of orbitals by atoms ??
    self.atom2mu_s = np.zeros((self.natm+1), dtype=np.int64)
    for atom,sp in enumerate(self.atom2sp):
        self.atom2mu_s[atom+1]=self.atom2mu_s[atom]+self.ao_log.sp2nmult[sp]
    
    orb2m = self.get_orb2m()
    _siesta2blanko_csr(orb2m, self.hsx.s4_csr, self.hsx.orb_sc2orb_uc)

    for s in range(self.nspin):
      _siesta2blanko_csr(orb2m, self.hsx.spin2h4_csr[s], self.hsx.orb_sc2orb_uc)
    
    #t1 = timer()
    for k in range(self.nkpoints):
      for s in range(self.nspin):
        for n in range(self.norbs):
          _siesta2blanko_denvec(orb2m, self.wfsx.x[k,s,n,:,:])
    #t2 = timer(); print(t2-t1, 'rsh wfsx'); t1 = timer()

    
    self.sp2symbol = [str(ion['symbol'].replace(' ', '')) for ion in self.sp2ion]
    self.sp2charge = self.ao_log.sp2charge
    self.init_libnao()
    self.state = 'should be useful for something'

    # Trying to be similar to mole object from pySCF 
    self.nelectron = self.hsx.nelec
    self.spin = self.nspin
    self.verbose = 1 
    self.stdout = sys.stdout
    self.symmetry = False
    self.symmetry_subgroup = None
    self._built = True 
    self.max_memory = 20000
    self.incore_anyway = False
    self._atom = [(self.sp2symbol[sp], list(self.atom2coord[ia,:])) for ia,sp in enumerate(self.atom2sp)]
    return self

  def init_gpaw(self, calc, label="gpaw", cd='.', **kvargs):
    """
        use the data from a GPAW LCAO calculations as input to
        initialize system variables.

        Input parameters:
        -----------------
            calc: GPAW calculator
            label (optional, string): label used for the calculations
            chdir (optional, string): path to the directory in which are stored the
                data from gpaw
            kvargs (optional, dict): dictionary of optional arguments
                We may need a list of optional arguments!

        Example:
        --------
            from ase import Atoms
            from gpaw import GPAW
            fname = os.path.dirname(os.path.abspath(__file__))+'/h2o.gpw'
            if os.path.isfile(fname):
                # Import data from a previous gpaw calculations
                calc = GPAW(fname, txt=None) # read previous calculation if the file exists
            else:
                # Run first gpaw to initialize the calculator
                from gpaw import PoissonSolver
                atoms = Atoms('H2O', positions=[[0.0,-0.757,0.587], [0.0,+0.757,0.587], [0.0,0.0,0.0]])
                atoms.center(vacuum=3.5)
                convergence = {'density': 1e-7}     # Increase accuracy of density for ground state
                poissonsolver = PoissonSolver(eps=1e-14, remove_moment=1 + 3)     # Increase accuracy of Poisson Solver and apply multipole corrections up to l=1
                calc = GPAW(basis='dzp', xc='LDA', h=0.3, nbands=23, convergence=convergence, poissonsolver=poissonsolver, mode='lcao', txt=None)     # nbands must be equal to norbs (in this case 23)
                atoms.set_calculator(calc)
                atoms.get_potential_energy()    # Do SCF the ground state
                calc.write(fname, mode='all') # write DFT output

            from pyscf.nao import system_vars_c
            sv = system_vars_c().init_gpaw(calc)
    """
    try:
        import ase
        import gpaw
    except:
        raise ValueError("ASE and GPAW must be installed for using system_vars_gpaw")
    from pyscf.nao.m_system_vars_gpaw import system_vars_gpaw
    return system_vars_gpaw(self, calc, label="gpaw", chdir='.', **kvargs)
    
    
  # More functions for similarity with Mole
  def atom_symbol(self, ia): return self.sp2symbol[self.atom2sp[ia]]
  def atom_charge(self, ia): return self.sp2charge[self.atom2sp[ia]]
  def atom_charges(self): return np.array([self.sp2charge[sp] for sp in self.atom2sp], dtype='int64')
  def atom_coord(self, ia): return self.atom2coord[ia,:]
  def atom_coords(self): return self.atom2coord
  def nao_nr(self): return self.norbs
  def atom_nelec_core(self, ia): return self.sp2charge[self.atom2sp[ia]]-self.ao_log.sp2valence[self.atom2sp[ia]]
  def intor_symmetric(self, type_str):
    """ Uff ... """
    if type_str.lower()=='cint1e_ovlp_sph':
      mat = self.overlap_coo().todense()
    else:
      raise RuntimeError('not implemented...')
    return mat

  # More functions for convenience (see PDoS)
  def get_orb2j(self): return get_orb2j(self)
  def get_orb2m(self): return get_orb2m(self)
  def dos(self, zomegas): return system_vars_dos(self, zomegas)
  def pdos(self, zomegas): return system_vars_pdos(self, zomegas)

  def overlap_coo(self, **kvargs):   # Compute overlap matrix for the given system
    from pyscf.nao import overlap_coo
    return overlap_coo(self, **kvargs)

  def overlap_lil(self, **kvargs):   # Compute overlap matrix in list of lists format
    from pyscf.nao.m_overlap_lil import overlap_lil
    return overlap_lil(self, **kvargs)

  def dipole_coo(self, **kvargs):   # Compute dipole matrix elements for the given system
    from pyscf.nao.m_dipole_coo import dipole_coo
    return dipole_coo(self, **kvargs)
  
  def overlap_check(self, tol=1e-5, **kvargs): # Works only after init_siesta_xml(), extend ?
    return overlap_check(self, tol=1e-5, **kvargs)

  def diag_check(self, atol=1e-5, rtol=1e-4, **kvargs): # Works only after init_siesta_xml(), extend ?
    return diag_check(self, atol, rtol, **kvargs)

  def vxc_lil(self, dm, xc_code, **kvargs):   # Compute exchange-correlation potentials
    from pyscf.nao.m_vxc_lil import vxc_lil
    return vxc_lil(self, dm, xc_code, deriv=1, **kvargs)

  def exc(self, dm, xc_code, **kvargs):   # Compute exchange-correlation energies
    from pyscf.nao.m_exc import exc
    return exc(self, dm, xc_code, **kvargs)

  def build_3dgrid(self, level=3):
    """ Build a global grid and weights for a molecular integration (integration in 3-dimensional coordinate space) """
    from pyscf import dft
    from pyscf.nao.m_gauleg import leggauss_ab
    grid = dft.gen_grid.Grids(self)
    grid.level = level # precision as implemented in pyscf
    grid.radi_method=leggauss_ab
    atom2rcut=np.zeros(self.natoms)
    for ia,sp in enumerate(self.atom2sp): atom2rcut[ia] = self.ao_log.sp2rcut[sp]
    grid.build(atom2rcut=atom2rcut)
    return grid

  def dens_elec(self, coords, dm):
    """ Compute electronic density for a given density matrix and on a given set of coordinates """
    from pyscf.nao.m_dens_libnao import dens_libnao
    from pyscf.nao.m_init_dm_libnao import init_dm_libnao
    from pyscf.nao.m_init_dens_libnao import init_dens_libnao
    if not self.init_sv_libnao : raise RuntimeError('not self.init_sv_libnao')
    if init_dm_libnao(dm) is None : raise RuntimeError('init_dm_libnao(dm) is None')
    if init_dens_libnao()!=0 : raise RuntimeError('init_dens_libnao()!=0')
    return dens_libnao(coords, self.nspin)

  def init_libnao(self, wfsx=None):
    """ Initialization of data on libnao site """
    from pyscf.nao.m_libnao import libnao
    from pyscf.nao.m_sv_chain_data import sv_chain_data
    from ctypes import POINTER, c_double, c_int64, c_int32

    if wfsx is None:
        data = sv_chain_data(self)
        # (nkpoints, nspin, norbs, norbs, nreim)
        size_x = np.array([1, self.nspin, self.norbs, self.norbs, 1], dtype=np.int32)
        libnao.init_sv_libnao.argtypes = (POINTER(c_double), POINTER(c_int64), POINTER(c_int32))
        libnao.init_sv_libnao(data.ctypes.data_as(POINTER(c_double)), c_int64(len(data)), size_x.ctypes.data_as(POINTER(c_int32)))
        self.init_sv_libnao = True
    else:
        size_x = np.zeros(len(self.wfsx.x.shape), dtype=np.int32)
        for i, sh in enumerate(self.wfsx.x.shape):
            size_x[i] = sh

        data = sv_chain_data(self)
        libnao.init_sv_libnao.argtypes = (POINTER(c_double), POINTER(c_int64), POINTER(c_int32))
        libnao.init_sv_libnao(data.ctypes.data_as(POINTER(c_double)), c_int64(len(data)), size_x.ctypes.data_as(POINTER(c_int32)))
        self.init_sv_libnao = True
    return self

  def dens_elec_vec(self, coords, dm):
    """ Electronic density: python vectorized version """
    from m_dens_elec_vec import dens_elec_vec
    return dens_elec_vec(self, coords, dm)
  
  def get_occupations(self, telec=None, ksn2e=None, fermi_energy=None):
    """ Compute occupations of electron levels according to Fermi-Dirac distribution """
    from pyscf.nao.m_fermi_dirac import fermi_dirac_occupations
    Telec = self.hsx.telec if telec is None else telec
    ksn2E = self.wfsx.ksn2e if ksn2e is None else ksn2e
    Fermi = self.fermi_energy if fermi_energy is None else fermi_energy
    ksn2fd = fermi_dirac_occupations(Telec, ksn2E, Fermi)
    ksn2fd = (3.0-self.nspin)*ksn2fd
    return ksn2fd

#
# Example of reading pySCF orbitals.
#
if __name__=="__main__":
  from pyscf import gto
  from pyscf.nao.m_system_vars import system_vars_c
  import matplotlib.pyplot as plt
  """ Interpreting small Gaussian calculation """
  mol = gto.M(atom='O 0 0 0; H 0 0 1; H 0 1 0; Be 1 0 0', basis='ccpvtz') # coordinates in Angstrom!
  sv = system_vars_c(gto=mol, tol=1e-8, nr=512, rmin=1e-5)
  
  print(sv.ao_log.sp2norbs)
  print(sv.ao_log.sp2nmult)
  print(sv.ao_log.sp2rcut)
  print(sv.ao_log.sp_mu2rcut)
  print(sv.ao_log.nr)
  print(sv.ao_log.rr[0:4], sv.ao_log.rr[-1:-5:-1])
  print(sv.ao_log.psi_log[0].shape, sv.ao_log.psi_log_rl[0].shape)

  sp = 0
  for mu,[ff,j] in enumerate(zip(sv.ao_log.psi_log[sp], sv.ao_log.sp_mu2j[sp])):
    nc = abs(ff).max()
    if j==0 : plt.plot(sv.ao_log.rr, ff/nc, '--', label=str(mu)+' j='+str(j))
    if j>0 : plt.plot(sv.ao_log.rr, ff/nc, label=str(mu)+' j='+str(j))

  plt.legend()
  #plt.xlim(0.0, 10.0)
  #plt.show()
