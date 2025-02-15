#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#
# Foster-Boys localization
#

import sys
import time
import numpy
from functools import reduce

from pyscf import lib
from pyscf.lib import logger
from pyscf.scf import ciah
from pyscf.lo import orth


def kernel(localizer, mo_coeff=None, callback=None, verbose=logger.NOTE):
    if mo_coeff is None:
        mo_coeff = numpy.asarray(localizer.mo_coeff, order='C')
    else:
        mo_coeff = numpy.asarray(mo_coeff, order='C')
        localizer.mo_coeff = mo_coeff

    if localizer.verbose >= logger.WARN:
        localizer.check_sanity()
    localizer.dump_flags()

    cput0 = (time.clock(), time.time())
    if isinstance(verbose, logger.Logger):
        log = verbose
    else:
        log = logger.Logger(localizer.stdout, verbose)
    if localizer.conv_tol_grad is None:
        conv_tol_grad = numpy.sqrt(localizer.conv_tol*.1)
        log.info('Set conv_tol_grad to %g', conv_tol_grad)
    else:
        conv_tol_grad = localizer.conv_tol_grad

    u0 = localizer.get_init_guess(localizer.init_guess)
    rotaiter = ciah.rotate_orb_cc(localizer, u0, conv_tol_grad, verbose=log)
    u, g_orb, stat = next(rotaiter)
    cput1 = log.timer('initializing CIAH', *cput0)

    tot_kf = stat.tot_kf
    tot_hop = stat.tot_hop
    conv = False
    e_last = 0
    for imacro in range(localizer.max_cycle):
        norm_gorb = numpy.linalg.norm(g_orb)
        u0 = lib.dot(u0, u)
        e = localizer.cost_function(u0)
        e_last, de = e, e-e_last

        log.info('macro= %d  f(x)= %.14g  delta_f= %g  |g|= %g  %d KF %d Hx',
                 imacro+1, e, de, norm_gorb, stat.tot_kf+1, stat.tot_hop)
        cput1 = log.timer('cycle= %d'%(imacro+1), *cput1)

        if (norm_gorb < conv_tol_grad and abs(de) < localizer.conv_tol):
            conv = True

        if callable(callback):
            callback(locals())

        if conv:
            break

        u, g_orb, stat = rotaiter.send(u0)
        tot_kf += stat.tot_kf
        tot_hop += stat.tot_hop

    rotaiter.close()
    log.info('macro X = %d  f(x)= %.14g  |g|= %g  %d intor %d KF %d Hx',
             imacro+1, e, norm_gorb,
             (imacro+1)*2, tot_kf+imacro+1, tot_hop)
    localizer.mo_coeff = lib.dot(mo_coeff, u0)
    return localizer.mo_coeff


def dipole_integral(mol, mo_coeff):
    # The gauge origin has no effects for maximization |<r>|^2
    # Set to charge center for physical significance of <r>
    charge_center = numpy.einsum('z,zx->x', mol.atom_charges(), mol.atom_coords())
    mol.set_common_orig(charge_center)
    dip = numpy.asarray([reduce(lib.dot, (mo_coeff.T, x, mo_coeff))
                         for x in mol.intor_symmetric('int1e_r', comp=3)])
    return dip

def atomic_init_guess(mol, mo_coeff):
    s = mol.intor_symmetric('int1e_ovlp')
    c = orth.orth_ao(mol, s=s)
    mo = reduce(numpy.dot, (c.T, s, mo_coeff))
    nmo = mo_coeff.shape[1]
# Find the AOs which have largest overlap to MOs
    idx = numpy.argsort(numpy.einsum('pi,pi->p', mo, mo))
    nmo = mo.shape[1]
    idx = idx[-nmo:]
    u, w, vh = numpy.linalg.svd(mo[idx])
    return lib.dot(vh, u.T)

class Boys(ciah.CIAHOptimizer):
    def __init__(self, mol, mo_coeff=None):
        ciah.CIAHOptimizer.__init__(self)
        self.mol = mol
        self.stdout = mol.stdout
        self.verbose = mol.verbose
        self.conv_tol = 1e-7
        self.conv_tol_grad = None
        self.max_cycle = 100
        self.max_iters = 20
        self.max_stepsize = .05
        self.ah_trust_region = 3
        self.ah_start_tol = 1e9
        self.ah_max_cycle = 40
        self.init_guess = 'atomic'

        self.mo_coeff = numpy.asarray(mo_coeff, order='C')
        self._keys = set(self.__dict__.keys())

    def dump_flags(self):
        log = logger.Logger(self.stdout, self.verbose)
        log.info('\n')
        log.info('******** %s flags ********', self.__class__)
        log.info('conv_tol = %s'       ,self.conv_tol       )
        log.info('conv_tol_grad = %s'  ,self.conv_tol_grad  )
        log.info('max_cycle = %s'      ,self.max_cycle      )
        log.info('max_stepsize = %s'   ,self.max_stepsize   )
        log.info('max_iters = %s'      ,self.max_iters      )
        log.info('kf_interval = %s'    ,self.kf_interval    )
        log.info('kf_trust_region = %s',self.kf_trust_region)
        log.info('ah_start_tol = %s'   ,self.ah_start_tol   )
        log.info('ah_start_cycle = %s' ,self.ah_start_cycle )
        log.info('ah_level_shift = %s' ,self.ah_level_shift )
        log.info('ah_conv_tol = %s'    ,self.ah_conv_tol    )
        log.info('ah_lindep = %s'      ,self.ah_lindep      )
        log.info('ah_max_cycle = %s'   ,self.ah_max_cycle   )
        log.info('ah_trust_region = %s',self.ah_trust_region)

    def gen_g_hop(self, u):
        mo_coeff = lib.dot(self.mo_coeff, u)
        dip = dipole_integral(self.mol, mo_coeff)
        g0 = numpy.einsum('xii,xip->pi', dip, dip)
        g = -self.pack_uniq_var(g0-g0.T) * 2

        h_diag = numpy.einsum('xii,xpp->pi', dip, dip) * 2
        h_diag-= g0.diagonal() + g0.diagonal().reshape(-1,1)
        h_diag+= numpy.einsum('xip,xip->pi', dip, dip) * 2
        h_diag+= numpy.einsum('xip,xpi->pi', dip, dip) * 2
        h_diag = -self.pack_uniq_var(h_diag) * 2

        #:nmo = mo_coeff.shape[1]
        #:h = numpy.einsum('xjj,xjq,pk->pjqk', dip, dip, numpy.eye(nmo))
        #:h+= numpy.einsum('xqq,xjq,pk->pjqk', dip, dip, numpy.eye(nmo))
        #:h+= numpy.einsum('xjq,xjp,jk->pjqk', dip, dip, numpy.eye(nmo))
        #:h+= numpy.einsum('xjp,xkp,pq->pjqk', dip, dip, numpy.eye(nmo))
        #:h-= numpy.einsum('xjj,xkp,jq->pjqk', dip, dip, numpy.eye(nmo))
        #:h-= numpy.einsum('xpp,xjq,pk->pjqk', dip, dip, numpy.eye(nmo))
        #:h-= numpy.einsum('xjp,xpq,pk->pjqk', dip, dip, numpy.eye(nmo))*2
        #:h = h - h.transpose(0,1,3,2)
        #:h = h - h.transpose(1,0,2,3)
        #:h = h + h.transpose(2,3,0,1)
        #:h *= -.5
        #:idx = numpy.tril_indices(nmo, -1)
        #:h = h[idx][:,idx[0],idx[1]]

        g0 = g0 + g0.T
        def h_op(x):
            x = self.unpack_uniq_var(x)
            norb = x.shape[0]
            #:hx = numpy.einsum('qp,xjj,xjq->pj', x, dip, dip)
            #:hx+= numpy.einsum('qp,xqq,xjq->pj', x, dip, dip)
            #:hx+= numpy.einsum('jk,xkk,xkp->pj', x, dip, dip)
            #:hx+= numpy.einsum('jk,xpp,xkp->pj', x, dip, dip)
            #:hx+= numpy.einsum('qj,xjq,xjp->pj', x, dip, dip)
            #:hx+= numpy.einsum('pk,xjp,xkp->pj', x, dip, dip)
            #:hx-= numpy.einsum('qp,xpp,xjq->pj', x, dip, dip) * 2
            #:hx-= numpy.einsum('qp,xjp,xpq->pj', x, dip, dip) * 2
            #:hx+= numpy.einsum('qj,xjp,xjq->pj', x, dip, dip)
            #:hx+= numpy.einsum('pk,xkp,xjp->pj', x, dip, dip)
            #:hx-= numpy.einsum('jk,xjj,xkp->pj', x, dip, dip) * 2
            #:hx-= numpy.einsum('jk,xkj,xjp->pj', x, dip, dip) * 2
            #:return -self.pack_uniq_var(hx)
            #:hx = numpy.einsum('iq,qp->pi', g0, x)
            hx = lib.dot(x.T, g0.T)
            #:hx+= numpy.einsum('qi,xiq,xip->pi', x, dip, dip) * 2
            hx+= numpy.einsum('xip,xi->pi', dip, numpy.einsum('qi,xiq->xi', x, dip)) * 2
            #:hx-= numpy.einsum('qp,xpp,xiq->pi', x, dip, dip) * 2
            hx-= numpy.einsum('xpp,xip->pi', dip,
                              lib.dot(dip.reshape(-1,norb), x).reshape(3,norb,norb)) * 2
            #:hx-= numpy.einsum('qp,xip,xpq->pi', x, dip, dip) * 2
            hx-= numpy.einsum('xip,xp->pi', dip, numpy.einsum('qp,xpq->xp', x, dip)) * 2
            return -self.pack_uniq_var(hx-hx.T)

        return g, h_op, h_diag

    def get_grad(self, u=None):
        if u is None: u = numpy.eye(self.mo_coeff.shape[1])
        mo_coeff = lib.dot(self.mo_coeff, u)
        dip = dipole_integral(self.mol, mo_coeff)
        g0 = numpy.einsum('xii,xip->pi', dip, dip)
        g = -self.pack_uniq_var(g0-g0.T) * 2
        return g

    def cost_function(self, u=None):
        if u is None: u = numpy.eye(self.mo_coeff.shape[1])
        mo_coeff = lib.dot(self.mo_coeff, u)
        dip = dipole_integral(self.mol, mo_coeff)
        r2 = self.mol.intor_symmetric('int1e_r2')
        r2 = numpy.einsum('pi,pi->', mo_coeff, lib.dot(r2, mo_coeff))
        val = r2 - numpy.einsum('xii,xii->', dip, dip)
        return val * 2

    def get_init_guess(self, key='atomic'):
        if isinstance(key, str) and key.lower() == 'atomic':
            return atomic_init_guess(self.mol, self.mo_coeff)
        else:
            nmo = self.mo_coeff.shape[1]
            u0 = numpy.eye(nmo)
            if numpy.linalg.norm(self.get_grad(u0)) < 1e-5:
                # Add noise to kick initial guess out of saddle point
                dr = numpy.cos(numpy.arange((nmo-1)*nmo//2)) * 1e-3
                u0 = self.extract_rotation(dr)
            return u0

    kernel = kernel

BF = Boys


if __name__ == '__main__':
    from pyscf import gto, scf

    mol = gto.Mole()
    mol.atom = '''
         O   0.    0.     0.2
         H    0.   -0.5   -0.4
         H    0.    0.7   -0.2
      '''
    mol.basis = 'ccpvdz'
    mol.build()
    mf = scf.RHF(mol).run()

    mo = mf.mo_coeff[:,:3]
    loc = Boys(mol, mo)
    u0 = numpy.eye(3)
    dx = 1e-5
    g_num = []
    hdiag_num = []
    h_op, hdiag = loc.gen_g_hop(u0)[1:]
    for i in range(3):
        dr = numpy.zeros(3)
        dr[i] = dx
        u = loc.extract_rotation(dr)
        cf1 =-loc.cost_function(u0)
        cf2 =-loc.cost_function(u0.dot(u))
        cg1 = loc.get_grad(u0)
        cg2 = loc.get_grad(u0.dot(u))
        g_num.append((cf2-cf1)/dx)
        print('hx', abs(cg2-cg1-h_op(dr)).sum())
        hdiag_num.append(h_op(dr/dx)[i])
    print('g', numpy.array(g_num), loc.get_grad(u0)*2)
    print('hdiag', numpy.array(hdiag_num), hdiag)

    mo = Boys(mol).kernel(mf.mo_coeff[:,5:9], verbose=4)
