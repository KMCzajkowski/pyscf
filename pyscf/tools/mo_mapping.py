#!/usr/bin/env python

import re
from functools import reduce
import numpy
import scipy.linalg
from pyscf import gto
from pyscf.lib import logger
from pyscf import lo

def mo_map(mol1, mo1, mol2, mo2, base=0, tol=.5):
    '''Given two orbitals, based on their overlap <i|j>, search all
    orbital-pairs which have significant overlap.

    Returns:
        Two lists.  First list is the orbital-pair indices, second is the
        overlap value.
    '''
    s = gto.intor_cross('int1e_ovlp', mol1, mol2)
    s = reduce(numpy.dot, (mo1.T, s, mo2))
    idx = numpy.argwhere(abs(s) > tol) + base
    for i,j in idx:
        logger.info(mol1, '<mo-1|mo-2>  %d  %d  %12.8f',
                    i, j, s[i,j])
    return idx, s

def mo_1to1map(s):
    '''Given <i|j>, search for the 1-to-1 mapping between i and j.

    Returns:
        a list [j-close-to-i for i in <bra|]
    '''
    s1 = abs(s)
    like_input = []
    for i in range(s1.shape[0]):
        k = numpy.argmax(s1[i])
        like_input.append(k)
        s1[:,k] = 0
    return like_input

def mo_comps(aolabels_or_baslst, mol, mo_coeff, cart=False, orth_method='meta_lowdin'):
    '''Given AO(s), show how the AO(s) are distributed in MOs.

    Args:
        aolabels_or_baslst : filter function or AO labels or AO index
            If it's a function,  the AO indices are the items for which the
            function return value is true.

    Kwargs:
        cart : bool
            whether the orbital coefficients are based on cartesian basis.
        orth_method : str
            The localization method to generated orthogonal AO upon which the AO
            contribution are computed.  It can be one of 'meta_lowdin',
            'lowdin' or 'nao'.

    Returns:
        A list of float to indicate the total contributions (normalized to 1) of
        localized AOs

    Examples:

    >>> from pyscf import gto, scf
    >>> from pyscf.tools import mo_mapping
    >>> mol = gto.M(atom='H 0 0 0; F 0 0 1', basis='6-31g')
    >>> mf = scf.RHF(mol).run()
    >>> comp = mo_mapping.mo_comps('F 2s', mol, mf.mo_coeff)
    >>> print('MO-id    F-2s components')
    >>> for i,c in enumerate(comp):
    ...     print('%-3d      %.10f' % (i, c))
    MO-id    components
    0        0.0000066344
    1        0.8796915532
    2        0.0590259826
    3        0.0000000000
    4        0.0000000000
    5        0.0435028851
    6        0.0155889103
    7        0.0000000000
    8        0.0000000000
    9        0.0000822361
    10       0.0021017982
    '''
    import copy
    if cart and not mol.cart:
        assert(mo_coeff.shape[0] == mol.nao_nr(cart=True))
        mol = copy.copy(mol)
        mol.cart = True
    s = mol.intor_symmetric('int1e_ovlp')
    lao = lo.orth.orth_ao(mol, orth_method, s=s)

    idx = _aolabels2baslst(mol, aolabels_or_baslst)
    if len(idx) == 0:
        logger.warn(mol, 'Required orbitals are not found')
    mo1 = reduce(numpy.dot, (lao[:,idx].T, s, mo_coeff))
    s1 = numpy.einsum('ki,ki->i', mo1, mo1)
    return s1

def _aolabels2baslst(mol, aolabels_or_baslst, base=0):
    if callable(aolabels_or_baslst):
        baslst = [i for i,x in enumerate(mol.ao_labels())
                  if aolabels_or_baslst(x)]
    elif isinstance(aolabels_or_baslst, str):
        aolabels = re.sub(' +', ' ', aolabels_or_baslst.strip(), count=1)
        aolabels = re.compile(aolabels)
        baslst = [i for i,s in enumerate(mol.ao_labels())
                  if re.search(aolabels, s)]
    elif len(aolabels_or_baslst) > 0 and isinstance(aolabels_or_baslst[0], str):
        aolabels = [re.compile(re.sub(' +', ' ', x.strip(), count=1))
                    for x in aolabels_or_baslst]
        baslst = [i for i,t in enumerate(mol.ao_labels())
                  if any(re.search(x, t) for x in aolabels)]
    else:
        baslst = [i-base for i in aolabels_or_baslst]
    return numpy.asarray(baslst, dtype=int)
