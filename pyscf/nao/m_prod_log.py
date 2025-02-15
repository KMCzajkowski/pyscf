from __future__ import print_function, division
import numpy as np
from numpy import einsum
from pyscf.nao.m_dipole_ni import dipole_ni
from pyscf.nao.m_overlap_ni import overlap_ni
from pyscf.nao.m_overlap_am import overlap_am
from pyscf.nao import ao_matelem_c, ao_log_c


#
#
#
def overlap_check(prod_log, overlap_funct=overlap_ni, **kvargs):
  """ Computes the allclose(), mean absolute error and maximal error of the overlap reproduced by the (local) vertex."""
  from pyscf.nao.m_ao_matelem import ao_matelem_c
  from pyscf.nao.m_ao_log import comp_moments
  me = ao_matelem_c(prod_log.rr, prod_log.pp).init_one_set(prod_log.ao_log)
  sp2mom0,sp2mom1 = comp_moments(prod_log)
  mael,mxel,acl=[],[],[]
  R0 = np.array([0.0,0.0,0.0])
  for sp,[vertex,mom0] in enumerate(zip(prod_log.sp2vertex,sp2mom0)):
    oo_ref = overlap_funct(me,sp,R0,sp,R0,**kvargs)
    oo = np.einsum('pjk,p->jk', vertex, mom0)
    ac = np.allclose(oo_ref, oo, atol=prod_log.tol_loc*10, rtol=prod_log.tol_loc)
    mae = abs(oo_ref-oo).sum()/oo.size
    mxe = abs(oo_ref-oo).max()
    acl.append(ac); mael.append(mae); mxel.append(mxe)
    if not ac: print('overlap check:', sp, mae, mxe, prod_log.tol_loc) 
  return mael,mxel,acl

#
#
#
def dipole_check(sv, prod_log, dipole_funct=dipole_ni, **kvargs):
  """ Computes the allclose(), mean absolute error and maximal error of the dipoles reproduced by the (local) vertex. """
  from pyscf.nao.m_ao_matelem import ao_matelem_c
  from pyscf.nao.m_ao_log import comp_moments
  me = ao_matelem_c(prod_log.ao_log)
  sp2mom0,sp2mom1 = comp_moments(prod_log)
  mael,mxel,acl=[],[],[]
  for atm,[sp,coord] in enumerate(zip(sv.atom2sp,sv.atom2coord)):
    dip_moms = np.einsum('j,k->jk', sp2mom0[sp],coord)+sp2mom1[sp]
    koo2dipme = np.einsum('pab,pc->cab', prod_log.sp2vertex[sp],dip_moms) 
    dipme_ref = dipole_funct(me,sp,coord,sp,coord, **kvargs)
    ac = np.allclose(dipme_ref, koo2dipme, atol=prod_log.tol_loc*10, rtol=prod_log.tol_loc)
    mae = abs(koo2dipme-dipme_ref).sum()/koo2dipme.size
    mxe = abs(koo2dipme-dipme_ref).max()
    acl.append(ac); mael.append(mae); mxel.append(mxe)
    if not ac: print('dipole check:', sp, mae, mxe, prod_log.tol_loc)
  return mael,mxel,acl

#
#
#
class prod_log_c(ao_log_c):
  '''
  Holder of (local) product functions and vertices.
  Args:
    ao_log, i.e. holder of the numerical orbitals
    tol : tolerance to keep the linear combinations
  Returns:
    for each specie returns a set of radial functions defining a product basis
    These functions are sufficient to represent the products of original atomic orbitals
    via a product vertex coefficients.
  Examples:
  '''
  def __init__(self):
    ao_log_c.__init__(self) # only log_mesh will be initialized and all the procedures from the class ao_log.
    return

  def init_prod_log_df(self, auxmol, sv, rcut_tol=1e-7):
    """ Initializes the radial functions from pyscf"""
    from pyscf.df.incore import aux_e2
    self.init_log_mesh(sv.ao_log.rr, sv.ao_log.pp)
    self.auxmol = auxmol
    ao_log_c.__init__(self)
    self.init_ao_log_gto_lm(auxmol, sv, sv.ao_log, rcut_tol)
    j3c = aux_e2(sv.mol, auxmol, intor='cint3c2e_sph', aosym='s1')
    nao = sv.mol.nao_nr()
    naoaux = auxmol.nao_nr()
    j3c = j3c.reshape(nao,nao,naoaux)
    #print(nao, naoaux)
    return self

  
  def init_prod_log_dp(self, ao_log, tol_loc=1e-5):
    """ Builds linear combinations of the original orbital products """
    from scipy.sparse import csr_matrix
    from pyscf.nao.m_local_vertex import local_vertex_c
    
    self.ao_log = ao_log
    self.init_log_mesh(ao_log.rr, ao_log.pp)
    self.nspecies = ao_log.nspecies
    self.tol_loc = tol_loc
    self.rr,self.pp,self.nr = ao_log.rr,ao_log.pp,ao_log.nr
    self.interp_rr = ao_log.interp_rr
    self.sp2nmult = np.zeros((ao_log.nspecies), dtype=np.int64)
    
    lvc = local_vertex_c(ao_log) # constructor of local vertices
    self.psi_log       = [] # radial orbitals: list of numpy arrays
    self.psi_log_rl    = [] # radial orbitals times r**j: list of numpy arrays
    self.sp_mu2rcut    = [] # list of numpy arrays containing the maximal radii
    self.sp_mu2j       = [] # list of numpy arrays containing the angular momentum of the radial function
    self.sp_mu2s       = [] # list of numpy arrays containing the starting index for each radial multiplett
    self.sp2vertex     = [] # list of numpy arrays containing the vertex coefficients <mu,a,b>
    self.sp2lambda     = [] # list of numpy arrays containing the inverse vertex coefficients <p,a,b> L^p_ab defined by F^p(r) = L^p_ab f^a(r) f^b(r)
    self.sp2vertex_csr = [] # going to be list of sparse matrices with dimension (nprod,norbs**2) or <mu,ab> . This is a derivative of the sp2vertex
    self.sp2inv_vv     = [] # this is a future list of matrices (<mu|ab><ab|nu>)^-1. This is a derivative of the sp2vertex
    self.sp2norbs      = [] # number of orbitals per specie
    self.sp2charge     = ao_log.sp2charge # copy of nuclear charges from atomic orbitals
    
    for sp,no in enumerate(lvc.ao1.sp2norbs):
      ldp = lvc.get_local_vertex(sp)

      mu2jd = []
      for j,evs in enumerate(ldp['j2eva']):
        for domi,ev in enumerate(evs):
          if ev>tol_loc: mu2jd.append([j,domi])
      
      nmult=len(mu2jd)
      mu2j = np.array([jd[0] for jd in mu2jd], dtype=np.int32)
      mu2s = np.array([0]+[sum(2*mu2j[0:mu+1]+1) for mu in range(nmult)], dtype=np.int64)
      mu2rcut = np.array([ao_log.sp2rcut[sp]]*nmult, dtype=np.float64)
      
      self.sp2nmult[sp]=nmult
      self.sp_mu2j.append(mu2j)
      self.sp_mu2rcut.append(mu2rcut)
      self.sp_mu2s.append(mu2s)
      self.sp2norbs.append(mu2s[-1])

      mu2ff = np.zeros((nmult, lvc.nr))
      for mu,[j,domi] in enumerate(mu2jd): mu2ff[mu,:] = ldp['j2xff'][j][domi,:]
      self.psi_log.append(mu2ff)
      
      mu2ff = np.zeros((nmult, lvc.nr))
      for mu,[j,domi] in enumerate(mu2jd): mu2ff[mu,:] = ldp['j2xff'][j][domi,:]/lvc.rr**j
      self.psi_log_rl.append(mu2ff)
       
      npf= sum(2*mu2j+1)  # count number of product functions
      mu2ww = np.zeros((npf,no,no))
      for [j,domi],s in zip(mu2jd,mu2s): mu2ww[s:s+2*j+1,:,:] = ldp['j2xww'][j][domi,0:2*j+1,:,:]
      self.sp2vertex.append(mu2ww)
      
      self.sp2vertex_csr.append(csr_matrix(mu2ww.reshape([npf,no**2])))
      v_csr = self.sp2vertex_csr[sp]
      self.sp2inv_vv.append( np.linalg.inv( (v_csr * v_csr.transpose() ).todense() ))

      #mu2iww = np.zeros((npf,no,no)) # rigorous way of doing it (but does not work)
      #for [j,domi],s in zip(mu2jd,mu2s): mu2iww[s:s+2*j+1,:,:] = ldp['j2xww_inv'][j][domi,0:2*j+1,:,:]
      #self.sp2lambda.append(mu2iww)

      mu2iww = np.array(self.sp2inv_vv[sp]*self.sp2vertex_csr[sp]).reshape([npf,no,no]) # lazy way of finding lambda
      self.sp2lambda.append(mu2iww)

    self.jmx = np.amax(np.array( [max(mu2j) for mu2j in self.sp_mu2j], dtype=np.int32))
    self.sp2rcut = np.array([np.amax(rcuts) for rcuts in self.sp_mu2rcut])
    
    del v_csr, mu2iww, mu2ww, mu2ff # maybe unnecessary
    return self
  ###

  def overlap_check(self, overlap_funct=overlap_ni, **kvargs):
    """ Recompute the overlap between orbitals using the product vertex and scalar moments of product functions""" 
    return overlap_check(self, overlap_funct=overlap_ni, **kvargs)

  def hartree_pot(self, **kvargs):
    """ Compute Hartree potential of the radial orbitals and return another ao_log_c storage with these potentials."""
    from pyscf.nao.m_ao_log_hartree import ao_log_hartree as ext
    return ext(self, **kvargs)

  def lambda_check_coulomb(self):
    """ Check the equality (p|q)<q,cd> = [p,ab] <ab|q>(q|r)<r|cd> """
    me = ao_matelem_c(self)
    mael,mxel=[],[]
    for sp,[pab,lab] in enumerate(zip(self.sp2vertex, self.sp2lambda)):
      pq = me.coulomb_am(sp,np.zeros(3), sp, np.zeros(3))
      pcd_ref = einsum('pq,qab->pab', pq, pab)
      abcd = einsum('abq,qcd->abcd', einsum('pab,pq->abq', pab,pq), pab)
      pcd = einsum('lab,abcd->lcd', lab, abcd)
      mael.append(abs(pcd-pcd_ref).sum()/pcd.size); mxel.append(abs(pcd-pcd_ref).max())
    return mael,mxel
    
  def lambda_check_overlap(self, overlap_funct=overlap_am, **kvargs):
    from pyscf.nao.m_ao_log import comp_moments
    """ Check the equality (p) = [p,ab] S^ab, i.e. scalar moments are recomputed with inversed vertex from the ao's overlap """
    me = ao_matelem_c(self.ao_log)
    sp2mom0,sp2mom1 = comp_moments(self)
    mael,mxel=[],[]
    for sp,[lab,mom0_ref] in enumerate(zip(self.sp2lambda,sp2mom0)):
      ab = overlap_funct(me,sp,np.zeros(3),sp,np.zeros(3),**kvargs)
      mom0 = einsum('lab,ab->l', lab,ab)
      mael.append((abs(mom0-mom0_ref)).sum()/mom0.size); mxel.append((abs(mom0-mom0_ref)).max())
    return mael,mxel

#
#
#
if __name__=='__main__':
  from pyscf.nao.m_system_vars import system_vars_c
  from pyscf.nao.m_prod_log import prod_log_c
  import matplotlib.pyplot as plt
  
  sv  = system_vars_c(label='siesta')
  prod_log = prod_log_c(sv.ao_log, tol_loc=1e-4)
  print(dir(prod_log))
  print(prod_log.sp2nmult, prod_log.sp2norbs)
  print(prod_log.overlap_check())
  print(prod_log.lambda_check_coulomb())

  sp = 0
  for mu,[ff,j] in enumerate(zip(prod_log.psi_log[sp], prod_log.sp_mu2j[sp])):
    if j==0: 
      plt.plot(prod_log.rr, ff/abs(ff).max(), "--", label=str(mu)+" j="+str(j))
    else: 
      plt.plot(prod_log.rr, ff/abs(ff).max(), label=str(mu)+" j="+str(j))
  
  plt.legend()
  plt.xlim(0.0,6.0)
  plt.show()
