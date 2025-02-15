import numpy as np

#
#
#
def log_interp(ff, r, rho_min_jt, dr_jt):
  """
    Interpolation of a function given on the logarithmic mesh (see m_log_mesh how this is defined)
    6-point interpolation on the exponential mesh (James Talman)
    Args:
      ff : function values to be interpolated
      r  : radial coordinate for which we want intepolated value
      rho_min_jt : log(rr[0]), i.e. logarithm of minimal coordinate in the logarithmic mesh
      dr_jt : log(rr[1]/rr[0]) logarithmic step of the grid
    Result: 
      Interpolated value

    Example:
      nr = 1024
      rr,pp = log_mesh(nr, rmin, rmax, kmax)
      rho_min, dr = log(rr[0]), log(rr[1]/rr[0])
      y = interp_log(ff, 0.2, rho, dr)
  """
  if r<=0.0: return ff[0]

  lr = np.log(r)
  k=int((lr-rho_min_jt)/dr_jt)
  nr = len(ff)
  k = min(max(k,2), nr-4)
  dy=(lr-rho_min_jt-k*dr_jt)/dr_jt

  fv = (-dy*(dy**2-1.0)*(dy-2.0)*(dy-3.0)*ff[k-2] 
       +5.0*dy*(dy-1.0)*(dy**2-4.0)*(dy-3.0)*ff[k-1] 
       -10.0*(dy**2-1.0)*(dy**2-4.0)*(dy-3.0)*ff[k]
       +10.0*dy*(dy+1.0)*(dy**2-4.0)*(dy-3.0)*ff[k+1]
       -5.0*dy*(dy**2-1.0)*(dy+2.0)*(dy-3.0)*ff[k+2]
       +dy*(dy**2-1.0)*(dy**2-4.0)*ff[k+3])/120.0 

  return fv

#
#
#
def comp_coeffs_(self, r, i2coeff):
  """
    Interpolation of a function given on the logarithmic mesh (see m_log_mesh how this is defined)
    6-point interpolation on the exponential mesh (James Talman)
    Args:
      r  : radial coordinate for which we want the intepolated value
    Result: 
      Array of weights to sum with the functions values to obtain the interpolated value coeff
      and the index k where summation starts sum(ff[k:k+6]*coeffs)
  """
  if r<=0.0:
    i2coeff.fill(0.0)
    i2coeff[0] = 1
    return 0

  lr = np.log(r)
  k  = int((lr-self.gammin_jt)/self.dg_jt)
  k  = min(max(k,2), self.nr-4)
  dy = (lr-self.gammin_jt-k*self.dg_jt)/self.dg_jt
  
  i2coeff[0] =     -dy*(dy**2-1.0)*(dy-2.0)*(dy-3.0)/120.0
  i2coeff[1] = +5.0*dy*(dy-1.0)*(dy**2-4.0)*(dy-3.0)/120.0
  i2coeff[2] = -10.0*(dy**2-1.0)*(dy**2-4.0)*(dy-3.0)/120.0
  i2coeff[3] = +10.0*dy*(dy+1.0)*(dy**2-4.0)*(dy-3.0)/120.0
  i2coeff[4] = -5.0*dy*(dy**2-1.0)*(dy+2.0)*(dy-3.0)/120.0
  i2coeff[5] =      dy*(dy**2-1.0)*(dy**2-4.0)/120.0

  return k-2

#
#
#
def comp_coeffs(self, r):
  i2coeff = np.zeros(6)
  k = comp_coeffs_(self, r, i2coeff)
  return k,i2coeff


class log_interp_c():
  """
    Interpolation of radial orbitals given on a log grid (m_log_mesh)
  """
  def __init__(self, gg):
    #assert(type(rr)==np.ndarray)
    assert(len(gg)>2)
    self.nr = len(gg)
    self.gammin_jt = np.log(gg[0])
    self.dg_jt = np.log(gg[1]/gg[0])

  def __call__(self, ff, r):
    assert ff.shape[-1]==self.nr
    k,cc = comp_coeffs(self, r)
    result = np.zeros(ff.shape[0:-2])
    for j,c in enumerate(cc): result = result + c*ff[...,j+k]
    return result
  
#    Example:
#      loginterp =log_interp_c(rr)

if __name__ == '__main__':
  from pyscf.nao.m_log_interp import log_interp, log_interp_c, comp_coeffs_
  from pyscf.nao.m_log_mesh import log_mesh
  rr,pp = log_mesh(1024, 0.01, 20.0)
  interp_c = log_interp_c(rr)
  gc = 0.234450
  ff = np.array([np.exp(-gc*r**2) for r in rr])
  rho_min_jt, dr_jt = np.log(rr[0]), np.log(rr[1]/rr[0]) 
  for r in np.linspace(0.01, 25.0, 100):
    yref = log_interp(ff, r, rho_min_jt, dr_jt)
    k,coeffs = comp_coeffs(interp_c, r)
    y = sum(coeffs*ff[k:k+6])
    if(abs(y-yref)>1e-15): print(r, yref, y, np.exp(-gc*r**2))
