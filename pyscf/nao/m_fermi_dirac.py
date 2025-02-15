from __future__ import print_function, division
import numpy as np

#
#
#
def fermi_dirac(telec, e, fermi_energy):
  """ Fermi-Dirac distribution function. """
  pw = (e-fermi_energy)/telec
  if pw>+100.0: return 0.0
  if pw<-100.0: return 1.0
  return 1.0/( 1.0+np.exp(pw) )


#
#
#
def fermi_dirac_occupations(telec, ksn2e, fermi_energy):
  """ Occupations according to the Fermi-Dirac distribution function. """
  assert telec>0.0
  assert type(fermi_energy)==float
  
  ksn2f = np.copy(ksn2e)
  for e in np.nditer(ksn2f, op_flags=['readwrite']): e[...] = fermi_dirac(telec, e, fermi_energy)

  return ksn2f

