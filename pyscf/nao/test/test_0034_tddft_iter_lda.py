from __future__ import print_function, division
import os,unittest,numpy as np

class KnowValues(unittest.TestCase):

  def test_tddft_iter_lda(self):
    """ Compute polarization with LDA TDDFT  """
    from timeit import default_timer as timer

    from pyscf.nao import system_vars_c, prod_basis_c, tddft_iter_c
    from pyscf.nao.m_comp_dm import comp_dm
    from timeit import default_timer as timer
    
    dname = os.path.dirname(os.path.abspath(__file__))
    sv = system_vars_c().init_siesta_xml(label='water', cd=dname)
    pb = prod_basis_c().init_prod_basis_pp(sv, jcutoff=7)
    td = tddft_iter_c(pb.sv, pb, tddft_iter_broadening=1e-2, xc_code='LDA,PZ', level=0)
    omegas = np.linspace(0.0,2.0,150)+1j*td.eps
    pxx = -td.comp_polariz_xx(omegas).imag
    data = np.array([omegas.real*27.2114, pxx])
    np.savetxt('water.tddft_iter_lda.omega.inter.pxx.txt', data.T, fmt=['%f','%f'])
    data_ref = np.loadtxt(dname+'/water.tddft_iter_lda.omega.inter.pxx.txt-ref')
    #print('    td.rf0_ncalls ', td.rf0_ncalls)
    #print(' td.matvec_ncalls ', td.matvec_ncalls)
    self.assertTrue(np.allclose(data_ref,data.T, rtol=1.0, atol=1e-05))


if __name__ == "__main__": unittest.main()
