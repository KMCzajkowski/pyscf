from __future__ import print_function, division
import os,unittest,numpy as np

class KnowValues(unittest.TestCase):

  def test_dens_elec(self):
    """ Compute density in coordinate space with system_vars_c, integrate and compare with number of electrons """
    from pyscf.nao import system_vars_c
    from pyscf.nao.m_comp_dm import comp_dm
    from timeit import default_timer as timer
    
    sv = system_vars_c().init_siesta_xml(label='water', cd=os.path.dirname(os.path.abspath(__file__)))
    dm = comp_dm(sv.wfsx.x, sv.get_occupations())
    #print(sv.get_occupations())
    #print(dir(sv.ao_log) )
    #print((sv.ao_log.psi_log[0][0]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[0][1]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[0][2]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[0][3]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[0][4]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #
    #print((sv.ao_log.psi_log[1][0]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[1][1]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    #print((sv.ao_log.psi_log[1][2]**2 *sv.ao_log.rr**3 * np.log(sv.ao_log.rr[1]/sv.ao_log.rr[0])).sum())
    
    grid = sv.build_3dgrid(level=5)
    
    #t1 = timer()
    #dens1 = sv.dens_elec_vec(grid.coords, dm)
    #t2 = timer(); print(t2-t1); t1 = timer()
    
    t1 = timer()
    dens = sv.dens_elec(grid.coords, dm)
    #t2 = timer(); print(t2-t1); t1 = timer()
    
    nelec = np.einsum("is,i", dens, grid.weights)[0]
    #t2 = timer(); print(t2-t1, nelec, sv.hsx.nelec, dens.shape); t1 = timer()

    self.assertAlmostEqual(nelec, sv.hsx.nelec, 2)
      
if __name__ == "__main__": unittest.main()
