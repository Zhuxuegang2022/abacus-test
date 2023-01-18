import os,sys,glob,re
from ..resultVasp import ResultVasp
from .. import comm
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

xfmlt = comm.XmlFindMultiLayerText
xfml = comm.XmlFindMultiLayer

class Vasp(ResultVasp):
    
    @ResultVasp.register(normal_end="if the job is normal ending")
    def GetNormalEnd(self):
        if len(self.OUTCAR) == 0:
            self['normal_end'] = None
            return
        elif len(self.OUTCAR) > 0 and "Voluntary context switches:" in self.OUTCAR[-1]:
            self['normal_end'] = True
            return
        else:
            self['normal_end'] = False

            print("Job is not normal ending!!! The latest 10 lines is:")
            if len(self.OUTCAR) < 10:
                print(''.join(self.OUTCAR))
            else:
                print(''.join(self.OUTCAR[-10:]))

    @ResultVasp.register(kpt="list, the K POINTS setting",
                         nkstot = "total K point number",
                         ibzk = "irreducible K point number")
    def GetKPT(self):
        if self.XMLROOT != None:
            tree = "./kpoints/generation/v[@name='divisions']"
            kpts = self.XMLROOT.find(tree)
            if kpts != None:
                nkstot = 1
                kpt = []
                for i in kpts.text.split():
                    nkstot *= int(i)
                    kpt.append(int(i))
                self['kpt'] = kpt
                self['nkstot'] = nkstot
            else:
                self['kpt'] = None
                self['nkstot'] = None

            tree = "./kpoints/varray[@name='kpointlist']/v"
            ibzk = self.XMLROOT.findall(tree)
            if ibzk != None:
                self['ibzk'] = len(ibzk)
            else:
                self['ibzk'] = None

    @ResultVasp.register(nbands="number of bands",
                         nelec = "total electron number",
                         spin = "the spin number",
                         encut = "Ry, the energy cutoff",
                         ismear = "the smearing method",
                         sigma = "the SIGMA setting of smearing, in eV",
                         nelm = "value of NELM, the setted maximum SCF steps",
                         natom = "total atom number")
    def GetInputSetting(self):
        if self.XMLROOT != None:
            tree = ".//separator[@name='electronic']/i[@name='NBANDS']"
            self['nbands'] = comm.iint(comm.XmlGetText(self.XMLROOT.find(tree)))

            tree = ".//separator[@name='electronic']/i[@name='NELECT']"
            self['nelec'] = comm.ifloat(comm.XmlGetText(self.XMLROOT.find(tree)))

            tree = ".//separator[@name='electronic spin']/i[@name='ISPIN']"
            self['spin'] = comm.iint(comm.XmlGetText(self.XMLROOT.find(tree)))
            
            tree = ".//separator[@name='electronic']/i[@name='ENMAX']"
            self['encut'] = comm.imath(comm.EV2RY,comm.ifloat(comm.XmlGetText(self.XMLROOT.find(tree))),"*")

            tree = ".//separator[@name='electronic smearing']/i[@name='ISMEAR']"
            self['ismear'] = comm.iint(comm.XmlGetText(self.XMLROOT.find(tree)))

            tree = ".//separator[@name='electronic smearing']/i[@name='SIGMA']"
            self['sigma'] = comm.ifloat(comm.XmlGetText(self.XMLROOT.find(tree)))
            
            tree = ".//separator[@name='electronic convergence']/i[@name='NELM']"
            self['nelm'] = comm.iint(comm.XmlGetText(self.XMLROOT.find(tree)))

            tree = "./atominfo/atoms"
            self['natom'] = comm.iint(comm.XmlGetText(self.XMLROOT.find(tree)))
            
        else:
            for line in self.OUTCAR:
                sline = line.split()
                if "number of bands    NBANDS" in line:
                    self['nbands'] = int(sline[-1])
                elif "number of ions     NIONS =" in line:
                    self['natom'] = int(sline[-1])
                elif "ISPIN  =" in line:
                    self['spin'] = int(sline[2])
                elif "ENCUT  =  " in line:
                    self['encut'] = float(sline[4])
                elif "NELECT =" in line:
                    self["nelec"] = float(sline[2])
                elif "ISMEAR =" in line:
                    self['ismear'] = sline[2].rstrip(";")
                    self["sigma"] = float(sline[5])
                elif "NELM   =" in line:
                    self['nelm'] = int(sline[2][:-1])

    @ResultVasp.register(ldautype = "value of LDAUTYPE, the type of plus U",
                         ldaul = "list, value of LDAUL, the l-quantum number of each element",
                         ldauu = "list, value of LDAUU, the U setting",
                         ldauj = "list, value of LDAUJ, the J setting")
    def GetLdaUSetting(self):
        for i,line in enumerate(self.OUTCAR):
            sline = line.split()
            if "LDA+U is selected," in line:
                self['ldautype'] = int(sline[-1])
                self['ldaul'] = [int(j) for j in self.OUTCAR[i+1].split("=")[-1].split()]
                self['ldauu'] = [float(j) for j in self.OUTCAR[i+2].split("=")[-1].split()]
                self['ldauj'] = [float(j) for j in self.OUTCAR[i+3].split("=")[-1].split()]
                break


    @ResultVasp.register(scf_steps = 'the steps of SCF, if is relax or md job, only last ION step is read',
                         converge = "if the SCF is converged. If scf_steps is smaller than NELM, will be converged, else is not converged")
    def GetSCFInfo(self):
        for i in range(len(self.OUTCAR)):
            j = -1*i - 1
            line = self.OUTCAR[j]
            if 'Iteration' in line:
                self['scf_steps'] = int(line.split('(')[1].split(')')[0])
                if self['scf_steps'] < self['nelm']:
                    self['converge'] = True
                else:
                    self['converge'] = False
                break
    
    @ResultVasp.register(energy = 'eV,the total energy',
                         energy_per_atom = 'eV, the energy divided by natom')
    def GetEnergy(self):
        for i in range(len(self.OUTCAR)):
            line = self.OUTCAR[-i-1]
            if "energy without entropy =" in line:
                self['energy'] = float(line.split()[4])
                if self['natom'] != None:
                    self['energy_per_atom'] = self['energy'] / self['natom']
                else:
                    self['energy_per_atom'] = None
                return
    
    @ResultVasp.register(force = 'list, eV/angstrom, the force of all atoms, [atom1x,atom1y,atom1z,atom2x,atom2y,atom2z...]',
                         stress = 'list, kBar, the stress, [xx,xy,xz,yx,yy,yz,zx,zy,zz]')
    def GetForceStress(self):
        force = []
        stress = []
        for i,line in enumerate(self.OUTCAR):
            if 'TOTAL-FORCE (eV/Angst)' in line:
                j = i+2
                while self.OUTCAR[j][:3] != " --":
                    force += [float(k) for k in self.OUTCAR[j].split()[3:6]]
                    j += 1
                self['force'] = force
            elif '  in kB' in line:
                s = [float(i) for i in line.split()[2:8]]
                self['stress'] = [s[0],s[3],s[5],s[3],s[1],s[4],s[5],s[4],s[2]]

    @ResultVasp.register(total_time = 'Total CPU time (s)',
                         scf_time = 'the total SCF times, s',
                         stress_time = 'the time of calculating stress')
                         
    def GetTimeInfo(self):
        stresst = None
        scft = 0
        for line in self.OUTCAR:
            if 'STRESS:  cpu time' in line:
                stresst = float(line.split()[-1])
            elif 'LOOP:  cpu time' in line:
                scft += float(line.split()[-1])
            elif 'Total CPU time used (sec):' in line:
                self['total_time'] = float(line.split()[-1])

        if stresst != None:
            self['stress_time'] = stresst
        if scft > 0:
            self['scf_time'] = scft

    @ResultVasp.register(total_mag = 'total magnization',
                         atom_mag = 'list, the magnization of each atom')
    def GetMagInfo(self):
        getatommag = False
        for i in range(len(self.OUTCAR)):
            i = -i-1
            line = self.OUTCAR[i]
            if line[:19] == " number of electron":
                self['total_mag'] = float(line.split()[-1])
                break
            elif not getatommag and line[:18] == ' magnetization (x)':
                j = i + 4
                atommag = []
                while self.OUTCAR[j][:3] != "---":
                    atommag.append(float(self.OUTCAR[j].split()[-1]))
                    j += 1
                self['atom_mag'] = atommag
                getatommag = True
                
    
    @ResultVasp.register(atom_name = 'list, the element name of each atom' ,
                         atom_type = 'list, the element name of each atomtype',
                         efermi     = 'the fermi energy, eV')
    def GetXMLInfo(self):
        if self.XMLROOT == None:
            return
        self['atom_name'] = comm.XmlGetText(self.XMLROOT.findall("./atominfo/array[@name='atoms']/set/rc/c[1]"))
        self['atom_type'] = comm.XmlGetText(self.XMLROOT.findall("./atominfo/array[@name='atomtypes']/set/rc/c[2]"))
        self['efermi'] = comm.XmlGetText(self.XMLROOT.findall("./calculation/dos/i[@name='efermi'][last()]"),func=float,idx = -1)

    @ResultVasp.register(band = '[[[]]], list with three dimension.dimension1: band, dimension2: kpoint, dimension3: spin')
    def GetBandInfo(self):
        if self.XMLROOT != None:
            band = []
            eigen = self.XMLROOT.findall('./calculation/eigenvalues/array')
            if eigen == None:
                self['band'] = None
            else:
                array = eigen[-1]
                for spin in array.find('set').findall('set'):
                    band.append([])
                    for kpoint in spin.findall('set'):
                        band[-1].append([])
                        for iband in kpoint.findall('r'):
                            band[-1][-1].append(float(iband.text.split()[0]))
                self['band'] = band

    @ResultVasp.register(band_gap = 'eV, the band gap')
    def GetBandGap(self):
        if self['band'] == None or self['efermi'] == None:
            self['band_gap'] = None
        else:
            vb = None
            cb = None
            fermi = self['efermi']
            for ispin in self['band']:
                for ik in ispin:
                    for i,iband in enumerate(ik):
                        if iband > fermi:
                            vb = iband if vb == None or vb > iband else vb
                            cb = ik[i-1] if cb == None or cb < ik[i-1] else cb
                            break
            #print("cb=%.5f, vb=%.5f" % (cb,vb))
            self['band_gap'] = None if vb == None or cb == None else vb - cb

