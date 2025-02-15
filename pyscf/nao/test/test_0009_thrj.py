from __future__ import print_function, division
import unittest

class KnowValues(unittest.TestCase):

  def test_thrj(self):
    """  """
    from pyscf.nao.m_thrj import thrj, thrj_nobuf
    from sympy.physics.wigner import wigner_3j
    for l1 in range(0,3):
      for l2 in range(0,3):
        for l3 in range(0,3):
          for m1 in range(-4,4+1):
            for m2 in range(-4,4+1):
              for m3 in range(-4,4+1):
                w3j1 = thrj(l1, l2, l3, m1, m2, m3)
                w3j2 = thrj_nobuf(l1, l2, l3, m1, m2, m3)
                w3j3 = float(wigner_3j(l1, l2, l3, m1, m2, m3))
                #print(w3j1, w3j2, w3j3, l1, l2, l3)
                self.assertAlmostEqual(w3j1, w3j2)
                self.assertAlmostEqual(w3j2, w3j3)
          
if __name__ == "__main__":
  unittest.main()
