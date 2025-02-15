#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

import copy
import numpy
from pyscf import lib
from pyscf import gto
from pyscf import ao2mo

# Obtained from http://www.psicode.org/psi4manual/master/basissets_byfamily.html
DEFAULT_AUXBASIS = {
# AO basis JK-fit MP2-fit
'ccpvdz'      : ('cc-pvdz-jkfit'          , 'cc-pvdz-ri'         ),
'ccpvdpdz'    : ('cc-pvdz-jkfit'          , 'cc-pvdz-ri'         ),
'augccpvdz'   : ('aug-cc-pvdz-jkfit'      , 'aug-cc-pvdz-ri'     ),
'augccpvdpdz' : ('aug-cc-pvdz-jkfit'      , 'aug-cc-pvdz-ri'     ),
'ccpvtz'      : ('cc-pvtz-jkfit'          , 'cc-pvtz-ri'         ),
'augccpvtz'   : ('aug-cc-pvtz-jkfit'      , 'aug-cc-pvtz-ri'     ),
'ccpvqz'      : ('cc-pvqz-jkfit'          , 'cc-pvqz-ri'         ),
'augccpvqz'   : ('aug-cc-pvqz-jkfit'      , 'aug-cc-pvqz-ri'     ),
'ccpv5z'      : ('cc-pv5z-jkfit'          , 'cc-pv5z-ri'         ),
'augccpv5z'   : ('aug-cc-pv5z-jkfit'      , 'aug-cc-pv5z-ri'     ),
'def2svp'     : ('def2-svp-jkfit'         , 'def2-svp-ri'        ),
'def2svpd'    : ('def2-svp-jkfit'         , 'def2-svpd-ri'       ),
'def2tzvp'    : ('def2-tzvp-jkfit'        , 'def2-tzvp-ri'       ),
'def2tzvpd'   : ('def2-tzvp-jkfit'        , 'def2-tzvpd-ri'      ),
'def2tzvpp'   : ('def2-tzvpp-jkfit'       , 'def2-tzvpp-ri'      ),
'def2tzvppd'  : ('def2-tzvpp-jkfit'       , 'def2-tzvppd-ri'     ),
'def2qzvp'    : ('def2-qzvp-jkfit'        , 'def2-qzvp-ri'       ),
'def2qzvpd'   : ('def2-qzvp-jkfit'        , None                 ),
'def2qzvpp'   : ('def2-qzvpp-jkfit'       , 'def2-qzvpp-ri'      ),
'def2qzvppd'  : ('def2-qzvpp-jkfit'       , 'def2-qzvppd-ri'     ),
'sto3g'       : ('def2-svp-jkfit'         , 'def2-svp-rifit'     ),
'321g'        : ('def2-svp-jkfit'         , 'def2-svp-rifit'     ),
'631g'        : ('cc-pvdz-jkfit'          , 'cc-pvdz-ri'         ),
'631+g'       : ('heavy-aug-cc-pvdz-jkfit', 'heavyaug-cc-pvdz-ri'),
'631++g'      : ('aug-cc-pvdz-jkfit'      , 'aug-cc-pvdz-ri'     ),
'6311g'       : ('cc-pvtz-jkfit'          , 'cc-pvtz-ri'         ),
'6311+g'      : ('heavy-aug-cc-pvtz-jkfit', 'heavyaug-cc-pvtz-ri'),
'6311++g'     : ('aug-cc-pvtz-jkfit'      , 'aug-cc-pvtz-ri'     ),
}

class load(ao2mo.load):
    '''load 3c2e integrals from hdf5 file
    Usage:
        with load(cderifile) as eri:
            print eri.shape
    '''
    def __init__(self, eri, dataname='j3c'):
        ao2mo.load.__init__(self, eri, dataname)


def aug_etb_for_dfbasis(mol, dfbasis='weigend', beta=2.3, start_at='Rb'):
    '''augment weigend basis with even tempered gaussian basis
    exps = alpha*beta^i for i = 1..N
    '''
    nuc_start = gto.mole._charge(start_at)
    uniq_atoms = set([a[0] for a in mol._atom])

    newbasis = {}
    for symb in uniq_atoms:
        nuc_charge = gto.mole._charge(symb)
        if nuc_charge < nuc_start:
            newbasis[symb] = dfbasis
        #?elif symb in mol._ecp:
        else:
            conf = lib.parameters.ELEMENTS[nuc_charge][2]
            max_shells = 4 - conf.count(0)
            emin_by_l = [1e99] * 8
            emax_by_l = [0] * 8
            for b in mol._basis[symb]:
                l = b[0]
                if l >= max_shells+1:
                    continue

                if isinstance(b[1], int):
                    e_c = numpy.array(b[2:])
                else:
                    e_c = numpy.array(b[1:])
                es = e_c[:,0]
                cs = e_c[:,1:]
                es = es[abs(cs).max(axis=1) > 1e-3]
                emax_by_l[l] = max(es.max(), emax_by_l[l])
                emin_by_l[l] = min(es.min(), emin_by_l[l])

            l_max = 8 - emax_by_l.count(0)
            emin_by_l = numpy.array(emin_by_l[:l_max])
            emax_by_l = numpy.array(emax_by_l[:l_max])
# Estimate the exponents ranges by geometric average
            emax = numpy.sqrt(numpy.einsum('i,j->ij', emax_by_l, emax_by_l))
            emin = numpy.sqrt(numpy.einsum('i,j->ij', emin_by_l, emin_by_l))
            liljsum = numpy.arange(l_max)[:,None] + numpy.arange(l_max)
            emax_by_l = [emax[liljsum==ll].max() for ll in range(l_max*2-1)]
            emin_by_l = [emin[liljsum==ll].min() for ll in range(l_max*2-1)]
            # Tune emin and emax
            emin_by_l = numpy.array(emin_by_l) * 2  # *2 for alpha+alpha on same center
            emax_by_l = numpy.array(emax_by_l) * 2  #/ (numpy.arange(l_max*2-1)*.5+1)

            ns = numpy.log((emax_by_l+emin_by_l)/emin_by_l) / numpy.log(beta)
            etb = [(l, max(n,1), emin_by_l[l], beta)
                   for l, n in enumerate(numpy.ceil(ns).astype(int))]
            newbasis[symb] = gto.expand_etbs(etb)

    return newbasis

def aug_etb(mol, beta=2.3):
    return aug_etb_for_dfbasis(mol, beta=beta, start_at=0)

def make_auxbasis(mol, mp2fit=False):
    '''Even-tempered Gaussians or the DF basis in DEFAULT_AUXBASIS'''
    uniq_atoms = set([a[0] for a in mol._atom])
    if isinstance(mol.basis, str):
        _basis = dict(((a, mol.basis) for a in uniq_atoms))
    elif 'default' in mol.basis:
        default_basis = mol.basis['default']
        _basis = dict(((a, default_basis) for a in uniq_atoms))
        _basis.update(mol.basis)
        del(_basis['default'])
    else:
        _basis = mol.basis

    auxbasis = {}
    for k in _basis:
        if isinstance(_basis[k], str):
            balias = gto.basis._format_basis_name(_basis[k])
            if gto.basis._is_pople_basis(balias):
                balias = balias.split('g')[0] + 'g'
            if balias in DEFAULT_AUXBASIS:
                if mp2fit:
                    auxb = DEFAULT_AUXBASIS[balias][1]
                else:
                    auxb = DEFAULT_AUXBASIS[balias][0]
                if auxb is not None and gto.basis.load(auxb, k):
                    auxbasis[k] = auxb

    if len(auxbasis) != len(_basis):
        # Some AO basis not found in DEFAULT_AUXBASIS
        auxbasis, auxdefault = aug_etb(mol), auxbasis
        auxbasis.update(auxdefault)
    return auxbasis

def make_auxmol(mol, auxbasis=None):
    '''Generate a fake Mole object which uses the density fitting auxbasis as
    the basis sets
    '''
    pmol = copy.copy(mol)  # just need shallow copy

    if auxbasis is None:
        auxbasis = make_auxbasis(mol)
    elif '+etb' in auxbasis:
        dfbasis = auxbasis[:-4]
        auxbasis = aug_etb_for_dfbasis(mol, dfbasis)
    pmol.basis = auxbasis

    if isinstance(auxbasis, (str, unicode, list, tuple)):
        uniq_atoms = set([a[0] for a in mol._atom])
        _basis = dict([(a, auxbasis) for a in uniq_atoms])
    elif 'default' in auxbasis:
        uniq_atoms = set([a[0] for a in mol._atom])
        _basis = dict(((a, auxbasis['default']) for a in uniq_atoms))
        _basis.update(auxbasis)
        del(_basis['default'])
    else:
        _basis = auxbasis
    pmol._basis = pmol.format_basis(_basis)

    pmol._atm, pmol._bas, pmol._env = \
            pmol.make_env(mol._atom, pmol._basis, mol._env[:gto.PTR_ENV_START])
    pmol._built = True
    lib.logger.debug(mol, 'auxbasis %s', auxbasis)
    lib.logger.debug(mol, 'num shells = %d, num cGTOs = %d',
                     pmol.nbas, pmol.nao_nr())
    return pmol
