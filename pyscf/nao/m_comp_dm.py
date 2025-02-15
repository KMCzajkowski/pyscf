from __future__ import print_function, division

#
def comp_dm(ksnac2x, ksn2occ):
  """
    Computes the density matrix 
    Args:
      ksnar2x : eigenvectors
      ksn2occ : occupations
    Returns:
      ksabc2dm : 
  """
  from numpy import einsum, zeros_like

  if ksnac2x.shape[-1]==2 : raise RuntimeError('check, please.')
  ksnac2x_occ = einsum('ksnac,ksn->ksnac', ksnac2x, ksn2occ)
  ksabc2dm = einsum('ksnac,ksnbc->ksabc', ksnac2x_occ, ksnac2x)

  return ksabc2dm
