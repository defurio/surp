#! /usr/bin/env/python

"""
Keeping with the structure of NRM_Model and how its drivers typically store data
this tool will allow the user to write out an oifits file (preferably calibrated)
given a directory where all the associated measurements are stored.

Alex Greenbaum agreenba@pha.jhu.edu Nov 2014
"""

from __future__ import print_function
import numpy as np
import oifits
import datetime
from scipy.special import comb
import sys,os
#rom nrm_analysis.misctools.utils import flip, rotatevectors, t3vis, t3err
from nrm_analysis.misctools.utils import                      t3vis, t3err
from nrm_analysis.misctools.mask_definitions import NRM_mask_definitions

def count_bls(ctrs):
    N = len(ctrs)
    nbl = N*(N-1)//2
    nbl = int(nbl)
    # labels uv points by holes they came from
    bl_label = np.zeros((nbl, 2))
    u = np.zeros(nbl)
    v = np.zeros(nbl)
    nn=0
    for ii in range(N-1):
        for jj in range(N-ii-1):
            #print nn+jj
            bl_label[nn+jj, :] = np.array([ii,ii+jj+1])
            u[nn+jj] = ctrs[ii,0] - ctrs[ii+jj+1,0]
            v[nn+jj] = ctrs[ii,1] - ctrs[ii+jj+1,1]
        nn = nn+jj+1
    return u,v,bl_label

def count_cps(ctrs):
    N = len(ctrs)
    ncps = int(comb(N,3))
    cp_label = np.zeros((ncps, 3))
    u1 = np.zeros(ncps)
    v1 = np.zeros(ncps)
    u2 = np.zeros(ncps)
    v2 = np.zeros(ncps)
    nn=0
    for ii in range(N-2):
        for jj in range(N-ii-2):
            for kk in range(N-ii-jj-2):
                #print '---------------'
                #print nn+kk
                cp_label[nn+kk,:] = np.array([ii, ii+jj+1, ii+jj+kk+2])
                u1[nn+kk] = ctrs[ii,0] - ctrs[ii+jj+1, 0]
                v1[nn+kk] = ctrs[ii,1] - ctrs[ii+jj+1, 1]
                u2[nn+kk] = ctrs[ii+jj+1,0] - ctrs[ii+jj+kk+2, 0]
                #print ii
                #print ii+jj+1, ii+jj+kk+2
                v2[nn+kk] = ctrs[ii+jj+1,1] - ctrs[ii+jj+kk+2, 1]
                #print u1[nn+kk], u2[nn+kk], v1[nn+kk], v2[nn+kk]
            nn = nn+kk+1
    return u1, v1, u2, v2, cp_label

def populate_symmamparray(blamp, N=7):
    #print blamp
    fringeamparray = np.zeros((N,N))
    step=0
    n=N-1
    for h in range(n):
        fringeamparray[h,h+1:] = blamp[step:step+n]
        step = step+n
        n=n-1
    fringeamparray = fringeamparray + fringeamparray.T
    return fringeamparray

def get_t3ampdata(v2s, v2errs, N = 10):
    varray = populate_symmamparray(np.sqrt(v2s), N=N)
    verrarray = populate_symmamparray(np.sqrt(v2errs), N=N)
    t3amps = np.zeros(int(comb(N,3)))
    t3amperr = np.zeros(int(comb(N,3)))
    nn=0
    for kk in range(N-2):
        for ii in range(N-kk-2):
            for jj in range(N-kk-ii-2):
                t3amps[nn+jj] = varray[kk, ii+kk+1] *\
                       varray[ii+kk+1, jj+ii+kk+2] *\
                       varray[jj+ii+kk+2, kk]
                t3amperr[nn+jj] = np.sqrt(verrarray[kk,ii+kk+1]**2 +\
                       verrarray[ii+kk+1, jj+ii+kk+2]**2 +\
                       verrarray[jj+ii+kk+2, kk]**2 )
            nn = nn+jj+1
    return t3amps, t3amperr

def read_in(path, wl=None, kw = 'CPs'):
    if wl==None:
        quant = np.loadtxt(path+kw+'.txt')
        err = np.loadtxt(path+kw+'err'+'.txt')
    else:
        quant = np.loadtxt(path+kw+'_'+str(wl)+'.txt')
        err = np.loadtxt(path+kw+'err_'+str(wl)+'.txt')
    return quant, err


class OIfits():

    def __init__(self,nrmobj, kwdict):
        """
        OIfits is an object that will make it easier to move fringe-fit 
        measurements into an oifits. For now it's using a generic
        'kwdict' so the user can load in what they want, maybe later
        I'll set the particular kwdict.
        """

        self.oif=oifits.oifits()
        # datapath tells OIfits where to read the measurements from]
        try:
            self.datapath = kwdict['path']
        except:
            self.datapath = ''

        self.N = len(nrmobj.ctrs)   
        self.nbl = int(self.N*(self.N-1)//2)
        self.ncps = int(comb(self.N,3))
        # Parse through kwdict to see what user decided to specify
        try:
            self.ra = kwdict['RA']
            self.dec = kwdict['DEC']
        except:
            self.ra = 0.0
            self.dec = 0.0
        try:
            self.timeobs = datetime.datetime(kwdict['year'],kwdict['month'],kwdict['day'])
        except:
            self.timeobs = datetime.datetime(2014,5,14)
        try:
            self.int_time = kwdict['int_time']
        except:
            self.int_time = 1e-5
        try:
            self.isname = kwdict['TEL']
        except:
            self.isname = 'Unknown'
        try:
            self.arrname = kwdict['arrname']
        except:
            self.arrname = 'Unknown'

        try:
            self.target = oifits.OI_TARGET(kwdict['object'], self.ra, \
                        self.dec, equinox=2000, veltyp = 'UNKNOWN')
        except:
            self.target = oifits.OI_TARGET('object', self.ra, self.dec, equinox=2000, \
                        veltyp='UNKNOWN')
        try:
            self.parang = kwdict['PARANG']
        except:
            self.parang = 0.0
        try:
            self.parang_range = kwdict['PARANGRANGE']
        except:
            self.parang_range = 0.0
        try:
            self.maskrotdeg = kwdict['maskrotdeg']
        except:
            print("no mask rotation")
            self.maskrotdeg=0
        try:
            self.phaseceil = kwdict['phaseceil']
        except:
            print("no phases will be flagged as bad")
            self.phaseceil=1e10
        """
        if 0:
            try: 
                # This really shouldn't be turned on but just in case the user is REALLY sure.
                self.flip = kwdict['flip']
            except:
                self.flip=False
        """
        try:
            self.covariance = kwdict["covariance"]
        except:
            self.covariance = None

        self.oitarget = np.array([self.target])

        # uv coordinates
        if kwdict['TEL'] == 'GEMINI':
            print('Gemini Telescope -- GPI data, rotating by 24.5 for lenslets')
            self.paoff = -24.5 # The lenslet rotation (cc)
        else:
            self.paoff = 0

        """
            # Again this should not have to be turned on.
            if self.flip == True:
                nrmobj.ctrs = rotatevectors(flip(rotatevectors(nrmobj.ctrs,\
                                self.maskrotdeg*np.pi/180.)),\
                        (-self.parang+self.paoff)*np.pi/180)
            # Rotate coordinates to get the correct sky position
            else:
                pass
                #nrmobj.ctrs = rotatevectors(nrmobj.ctrs,\
                #        (-self.parang+self.paoff+self.maskrotdeg)*np.pi/180.)
        """

        self.ucoord, self.vcoord, self.labels = count_bls(nrmobj.ctrs)
        # closure phase coordinates
        self.u1coord, self.v1coord, self.u2coord, self.v2coord,\
                    self.cplabels= count_cps(nrmobj.ctrs)

    def dummytables(self):
        # There are some oifits extensions that are not used by NRMers, so we
        # fill them with dummy entries here.
        station1 = station1=["Dummy Table","Dummy Table",0,0.45,[10.,20.,30.]]
        stations=[station1]
        self.array=oifits.OI_ARRAY("GEOCENTRIC",np.array([10.,20.,30.]),stations=stations)
        self.oiarray={self.arrname:self.array}
        self.station=self.oiarray[self.arrname].station[0] #will be used later

    def oi_data(self, read_from_txt=True, **kwargs):
        # this is where all the complex visibility measurements will be stored
        # April 2016 update: read from txt option, but also allow user to put in visibilities   
        # and errors in kwargs --- These should be in dimensions nwav, nbl/ncp

        #define oifits arrays
        self.oit3=[]
        self.oivis2=[]
        self.oivis=[]
        self.nwav=len(self.wls)

        # default is no flag -- can be reset by user after calling oi_data()
        self.v2flag = np.resize(False, (self.nwav, self.nbl))
        # will flag based on phaseceil parameter, below
        self.t3flag = np.zeros((self.nwav, self.ncps))
        if 0:
            print(self.wls)
            print(self.datapath)

        # default is read_from_txt -- looks in calibrated directory for these files
        if read_from_txt == True:
            # VIS2 part:
            self.v2 = np.ones((self.nwav, self.nbl))
            self.v2_err = self.v2.copy()
            self.vispha = np.ones((self.nwav, self.nbl))
            self.visphaerr = self.vispha.copy()

            if len(self.wls)==1:
                self.v2[0,:], self.v2_err[0,:] = read_in(self.datapath, kw='v2')
                self.vispha[0,:], self.viphaerr[0,:] = read_in(self.datapath, kw='pha')
            else:
                for qq,wl in enumerate(self.wls):
                    self.v2[qq,:], self.v2_err[qq,:] = read_in(self.datapath, wl=qq,kw='v2')
                    self.vispha[qq,:], self.viphaerr[qq,:] = read_in(self.datapath, kw='pha')

            # T3 info:
            self.t3amp = np.ones((self.nwav, self.ncps))
            self.t3phi = np.zeros((self.nwav, self.ncps))
            self.t3amperr = self.t3amp.copy()
            self.t3phierr = self.t3pha.copy()
            if len(self.wls)==1:
                self.t3phi[0,:], self.t3phierr[0,:] = read_in(self.datapath,kw='cp')
            else:
                for qq,wl in enumerate(self.wls):
                    self.t3phi[qq,:], self.t3phierr[qq,:] = read_in(self.datapath, wl=qq,kw='cp')
            for elem in range(self.t3amp.shape[0]):
                self.t3amp[elem,:] = t3vis(np.sqrt(self.v2[elem,:]), N=self.N)
                self.t3amperr[elem,:] = t3err(self.v2_err[elem, :], N=self.N)
        # or user can give the arrays as kwargs
        else:
            #self.wls = kwargs["wls"] # satisfied by wavextension
            if self.clip is not None:
                self.v2 = kwargs["v2"][self.clip[0]: self.clip[1]]
                self.v2_err = kwargs["v2err"][self.clip[0]: self.clip[1]]
                # Add in vis observables
                self.t3phi = kwargs["cps"][self.clip[0]: self.clip[1]]
                #print "cps given to oifits writer:"
                #print self.t3phi
                self.t3phierr = kwargs["cperr"][self.clip[0]: self.clip[1]]
                self.vispha = kwargs["pha"][self.clip[0]: self.clip[1]]
                self.visphaerr = kwargs["phaerr"][self.clip[0]: self.clip[1]]
            else:
                self.v2 = kwargs["v2"]
                self.v2_err = kwargs["v2err"]
                # Add in vis observables
                self.t3phi = kwargs["cps"]
                #print "cps given to oifits writer:"
                #print self.t3phi
                self.t3phierr = kwargs["cperr"]
                self.vispha = kwargs["pha"]
                self.visphaerr = kwargs["phaerr"]


        # T3 AMP data from V2 arrays
        self.t3amp = 0*self.t3phi.copy()
        self.t3amperr = 0*self.t3phierr.copy()
        #print self.t3amp.shape
        for elem in range(self.t3amp.shape[0]):
            self.t3amp[elem,:] = t3vis(np.sqrt(self.v2[elem,:]), N=self.N)#self.t3phi.copy() #np.ones((self.nwav, self.ncps))
            self.t3amperr[elem,:] = t3err(self.v2_err[elem, :], N=self.N)#self.t3phierr.copy() #np.ones((self.nwav, self.ncps))
        #for qq,wl in enumerate(self.wls):
        #   self.t3amp[qq,:], self.t3amperr[qq,:] = get_t3ampdata(np.sqrt(self.v2[qq,:]),\
        #                                   self.v2_err[qq,:], N=self.N)

        #print np.nan in np.isnan(self.v2)
        #print "break?"
        for qq in range(self.nbl):
            vis2data = oifits.OI_VIS2(self.timeobs,self.int_time, self.v2[:,qq],\
                self.v2_err[:,qq], self.v2flag[:,qq], self.ucoord[qq],\
                self.vcoord[qq], self.oiwav,self.target,array=self.array,\
                station=[self.station,self.station])
            self.oivis2.append(vis2data)

            visdata = oifits.OI_VIS(self.timeobs,self.int_time, np.sqrt(self.v2[:,qq]), \
                np.sqrt(self.v2_err[:,qq]), self.vispha, self.visphaerr, self.v2flag, \
                self.ucoord[qq], self.vcoord[qq], self.oiwav,self.target,array=self.array,\
                station=[self.station,self.station])
            self.oivis.append(visdata)

        #print 'oivis2 table set'
        self.oivis2 = np.array(self.oivis2)
        #self.oivis = np.array(self.oivis)
        "vis understood by oifits obj:"
        #print self.oivis
        #print self.oivis2

            #print read_in(self.datapath, wl,kw='cp')
            # needs to be in degrees
            #self.t3flag[abs(self.t3phi)>np.pi] = 1
            #self.t3flag[abs(self.t3phierr)>np.pi] = 1
        #print self.t3amperr

        #print "cps given to oifits writer, again:"
        #print self.t3phi
        print(np.shape(self.t3flag))
        print(np.shape(self.t3phi))
        print(np.shape(self.phaseceil))
        self.t3flag[abs(self.t3phi)>self.phaseceil]=1
        for i in range(int(self.ncps)):
            """self, timeobs, int_time, t3amp, t3amperr, t3phi, t3phierr, flag, u1coord,
            v1coord, u2coord, v2coord, wavelength, target, array=None, station=(None,None,None)"""
            self.t3data=oifits.OI_T3(self.timeobs,self.int_time,self.t3amp[:,i],\
                self.t3amperr[:,i],self.t3phi[:,i],self.t3phierr[:,i],\
                self.t3flag[:,i],self.u1coord[i],self.v1coord[i],\
                self.u2coord[i],self.v2coord[i],self.oiwav,self.target,\
                array=self.array,station=(self.station,self.station,self.station))
            self.oit3.append(self.t3data)
        self.oit3=np.array(self.oit3)
        #print "cps understood by oifits obj:"
        #print self.oit3
        #print self.oit3[2].t3amp, self.oit3[2].t3phi

    def wavextension(self, wls, eff_band, clip=None):#mode, fitsfile, clip=None):
        # The OI_WAVELENGTH table -- stores wavelength info

        # calls another convenient function to read GPI headers for
        # wavelengths -- pretty GPI specific, may have to deal with 
        # this later
        # April 2016: Maybe this is a place to have an instrument definition?
        """
        if self.mode == 'gpi_spect':
            print('SPECT MODE')
            self.wls  = wl_list(fitsfile)
            self.wls  = wavls
            if clip is not None:    
                self.wls = self.wls[clip:-clip]
            self.nwav = len(self.wls)
            self.eff_band = np.ones(self.nwav)*(self.wls[-1] - self.wls[0])/self.nwav
        elif self.mode == 'gpi_pol':
            # Should have lookup here for different bands?
            print('POL MODE')
            self.wls = np.array(['045','2268'])
            self.nwav = len(self.wls)
            tmpwls  = wl_list(fitsfile)
            self.eff_band = np.ones(self.nwav)*(tmpwls[-1] - tmpwls[0])
        else:
            print('NO MODE SPECIFIED')
            # must specify a monochromatic wavelength
            self.wls = np.array([self.wav_um,])
            self.nwav = len(self.wls)
            if not hasattr(self, "eff_band"):
                self.eff_band = np.ones(1)
        """
        #self.wavs = 1.0e-6*self.wls #np.arange(self.nwav)
        if clip is not None:
            if hasattr(clip, "__iter__"):
                self.clip = clip
                self.wls = wls[clip[0]:-clip[1]]
                self.eff_band = eff_band[clip[0]:-clip[1]]
            else:
                self.clip = [clip, -clip]
                self.wls = wls[clip:-clip]
                self.eff_band = eff_band[clip:-clip]
        else:
            self.clip=None
            self.wls = wls
            self.eff_band = eff_band
        self.oiwav=oifits.OI_WAVELENGTH(self.wls,eff_band=self.eff_band)
        self.wavs={self.isname:self.oiwav}
        return self.wavs

    def write(self, save_name):
        # The easy part, just write it out!

        self.veltyp = oifits.OI_ARRAY("VELTYP", "UNKNOWN")
        self.oif.array=self.oiarray
        self.oif.target=self.oitarget
        self.oif.wavelength=self.wavs
        self.oif.vis2=self.oivis2
        #self.oif.vis = self.oivis
        self.oif.t3=self.oit3
        # Add in vis array
        self.oif.vis=np.array([])
        # some extra keywords we'd like to hold onto
        self.oif.avparang = self.parang
        self.oif.parang_range = self.parang_range
        self.oif.covariance = self.covariance

        print(self.oif.wavelength)
        print(type(self.oif.wavelength))
        #from future.utils import iteritems
        #print(iteritems(self.oif.wavelength))

        self.oif.save(self.datapath+save_name)
        # Check
        f = oifits.open(self.datapath+save_name)
        #print "0th t3phi:", f.t3[0].t3phi
        #print "0th t3amp:", f.t3[0].t3amp
        return self.datapath+save_name

if __name__ == "__main__":


    maskname= 'gpi_g10s40'
    gpimask = NRM_mask_definitions(maskname = maskname)
    # example:
    mykeywords = {'TEL':'GEMINI','arrname':maskname }
    OIfits(gpimask,mykeywords)
