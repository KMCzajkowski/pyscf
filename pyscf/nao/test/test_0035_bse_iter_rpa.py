from __future__ import print_function, division
import os,unittest,numpy as np

class KnowValues(unittest.TestCase):

  def test_bse_iter_rpa(self):
    """ Compute polarization with LDA TDDFT  """
    from timeit import default_timer as timer
    from pyscf.nao import system_vars_c, prod_basis_c, bse_iter_c
    from timeit import default_timer as timer
    
    dname = os.path.dirname(os.path.abspath(__file__))
    sv = system_vars_c().init_siesta_xml(label='water', cd=dname)
    pb = prod_basis_c().init_prod_basis_pp(sv)
    bse = bse_iter_c(pb.sv, pb, iter_broadening=1e-2)
    omegas = np.linspace(0.0,2.0,500)+1j*bse.eps
    dab = [d.toarray() for d in sv.dipole_coo()]
    
    pxx = np.zeros(len(omegas))
    for iw,omega in enumerate(omegas):
      for ixyz in range(1):
        vab = bse.apply_l0(dab[ixyz], omega)
        pxx[iw] = pxx[iw] - (vab.imag*dab[ixyz]).sum()
        
    data = np.array([omegas.real*27.2114, pxx])
    #np.savetxt('water.bse_iter.omega.nonin.pxx.txt', data.T, fmt=['%f','%f'])
    data_ref = np.loadtxt(dname+'/water.bse_iter_rpa.omega.nonin.pxx.txt-ref')
    #print('    bse.l0_ncalls ', bse.l0_ncalls)
    self.assertTrue(np.allclose(data_ref,data.T, rtol=1.0, atol=1e-05))


if __name__ == "__main__": unittest.main()
