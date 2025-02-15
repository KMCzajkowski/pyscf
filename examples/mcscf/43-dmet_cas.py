#!/usr/bin/env python

from functools import reduce
import numpy
import scipy.linalg
from pyscf import scf
from pyscf import gto
from pyscf import mcscf, fci

'''
Triplet and quintet energy gap of Iron-Porphyrin molecule

In this example, we use density matrix embedding theory
(ref. Q Sun, JCTC, 10(2014), 3784) to generate initial guess.
'''

#
# For 3d transition metal, people usually consider the so-called double
# d-shell effects for CASSCF calculation.  Double d-shell here refers to 3d
# and 4d atomic orbitals.  Density matrix embedding theory (DMET) provides a
# method to generate CASSCF initial guess in terms of localized orbitals.
# Given DMET impurity and truncated bath, we can select Fe 3d and 4d orbitals
# and a few entangled bath as the active space.
#


##################################################
#
# Quintet
#
##################################################

mol = gto.Mole()
mol.atom = [
    ['Fe', (0.      , 0.0000  , 0.0000)],
    ['N' , (1.9764  , 0.0000  , 0.0000)],
    ['N' , (0.0000  , 1.9884  , 0.0000)],
    ['N' , (-1.9764 , 0.0000  , 0.0000)],
    ['N' , (0.0000  , -1.9884 , 0.0000)],
    ['C' , (2.8182  , -1.0903 , 0.0000)],
    ['C' , (2.8182  , 1.0903  , 0.0000)],
    ['C' , (1.0918  , 2.8249  , 0.0000)],
    ['C' , (-1.0918 , 2.8249  , 0.0000)],
    ['C' , (-2.8182 , 1.0903  , 0.0000)],
    ['C' , (-2.8182 , -1.0903 , 0.0000)],
    ['C' , (-1.0918 , -2.8249 , 0.0000)],
    ['C' , (1.0918  , -2.8249 , 0.0000)],
    ['C' , (4.1961  , -0.6773 , 0.0000)],
    ['C' , (4.1961  , 0.6773  , 0.0000)],
    ['C' , (0.6825  , 4.1912  , 0.0000)],
    ['C' , (-0.6825 , 4.1912  , 0.0000)],
    ['C' , (-4.1961 , 0.6773  , 0.0000)],
    ['C' , (-4.1961 , -0.6773 , 0.0000)],
    ['C' , (-0.6825 , -4.1912 , 0.0000)],
    ['C' , (0.6825  , -4.1912 , 0.0000)],
    ['H' , (5.0441  , -1.3538 , 0.0000)],
    ['H' , (5.0441  , 1.3538  , 0.0000)],
    ['H' , (1.3558  , 5.0416  , 0.0000)],
    ['H' , (-1.3558 , 5.0416  , 0.0000)],
    ['H' , (-5.0441 , 1.3538  , 0.0000)],
    ['H' , (-5.0441 , -1.3538 , 0.0000)],
    ['H' , (-1.3558 , -5.0416 , 0.0000)],
    ['H' , (1.3558  , -5.0416 , 0.0000)],
    ['C' , (2.4150  , 2.4083  , 0.0000)],
    ['C' , (-2.4150 , 2.4083  , 0.0000)],
    ['C' , (-2.4150 , -2.4083 , 0.0000)],
    ['C' , (2.4150  , -2.4083 , 0.0000)],
    ['H' , (3.1855  , 3.1752  , 0.0000)],
    ['H' , (-3.1855 , 3.1752  , 0.0000)],
    ['H' , (-3.1855 , -3.1752 , 0.0000)],
    ['H' , (3.1855  , -3.1752 , 0.0000)],
]
mol.basis = 'ccpvdz'
mol.verbose = 4
mol.output = 'fepor.out'
mol.spin = 4
mol.symmetry = True
mol.build()

mf = scf.ROHF(mol)
mf = scf.fast_newton(mf)
idx3d4d = [i for i,s in enumerate(mol.spheric_labels(1))
           if 'Fe 3d' in s or 'Fe 4d' in s]
ncas, nelecas, mo = dmet_cas.guess_cas(mf, mf.make_rdm1(), idx3d)
mc = mcscf.approx_hessian(mcscf.CASSCF(mf, ncas, nelecas)
mc.kernel(mo)
e_q = mc.e_tot  # -2244.82910509839







##################################################
#
# Triplet
#
##################################################

mol.spin = 2
mol.build(0, 0)  # (0, 0) to avoid dumping input file again

mf = scf.ROHF(mol)
mf = scf.fast_newton(mf)

#
# CAS(8e, 11o)
#
mf = scf.ROHF(mol)
mf = scf.fast_newton(mf)
idx3d4d = [i for i,s in enumerate(mol.spheric_labels(1))
           if 'Fe 3d' in s or 'Fe 4d' in s]
ncas, nelecas, mo = dmet_cas.guess_cas(mf, mf.make_rdm1(), idx3d)
mc = mcscf.approx_hessian(mcscf.CASSCF(mf, ncas, nelecas)
mc.kernel(mo)
e_t = mc.e_tot  # -2244.81493852189


print('E(T) = %.15g  E(Q) = %.15g  gap = %.15g' % (e_t, e_q, e_t-e_q))

