from __future__ import print_function, division
import os,unittest
from pyscf.nao import system_vars_c, prod_basis_c, tddft_iter_c
from numpy import allclose, float32, einsum

dname = os.path.dirname(os.path.abspath(__file__))
sv = system_vars_c().init_siesta_xml(label='water', cd=dname)
pb = prod_basis_c().init_prod_basis_pp(sv)

class KnowValues(unittest.TestCase):
  
  def test_vrtx_coo(self):
    """ This is to test the vertex in the sparse format """
    va = pb.get_dp_vertex_array()
    vc = pb.get_dp_vertex_coo().toarray().reshape([pb.npdp,pb.norbs,pb.norbs])
    self.assertTrue(abs(va).sum()>0.0)
    self.assertTrue(allclose(vc, va))

    va = pb.get_dp_vertex_array(dtype=float32)
    vc = pb.get_dp_vertex_coo(dtype=float32).toarray().reshape([pb.npdp,pb.norbs,pb.norbs])
    self.assertTrue(abs(va).sum()>0.0)
    self.assertTrue(allclose(vc, va))

  def test_vrtx_pab(self):
    """ This is to test the atom-centered vertex in the form of dense array """
    dab2v = pb.get_dp_vertex_array()
    dp2c = pb.get_da2cc_den()
    pab2v1 = einsum('dp,dab->pab', dp2c, dab2v)
    pab2v2 = pb.get_ac_vertex_array()
    self.assertTrue(allclose(pab2v1,pab2v2))

  def test_cc_coo(self):
    """ This is to test the gathering of conversion coefficients into a sparse format """
    cc_coo = pb.get_da2cc_coo().toarray()
    cc_den = pb.get_da2cc_den()
    self.assertTrue(allclose(cc_coo, cc_den) )
    cc_coo = pb.get_da2cc_coo(float32).toarray()
    cc_den = pb.get_da2cc_den(float32)
    self.assertTrue(allclose(cc_coo, cc_den) )

  def test_tddft_iter(self):
    """ This is iterative TDDFT with SIESTA starting point """
    td = tddft_iter_c(pb.sv, pb)
    self.assertTrue(hasattr(td, 'x'))
    self.assertTrue(td.ksn2f.sum()==8.0) # water: O -- 6 electrons in the valence + H2 -- 2 electrons
    self.assertEqual(td.xocc.shape[0], 4)
    self.assertEqual(td.xvrt.shape[0], 19)

    dn0 = td.apply_rf0(td.moms1[:,0])
    

if __name__ == "__main__":
  unittest.main()
