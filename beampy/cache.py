# -*- coding: utf-8 -*-

"""
Part of beampy project

Manage cache system for slides
"""

import os, sys

try:
    import cPickle as pkl
except:
    #compatibility with python 3.x
    import pickle as pkl

import gzip
import copy
import hashlib
import tempfile
import glob

class cache_slides():

    def __init__(self, cache_dir, document):
        """
            Create a cache_slides object to store cache in the given cache folder
        """
        self.folder = cache_dir
        self.version = document.__version__
        self.global_store = document._global_store
        self.data = {} #Cache data are stored in a dict

        self.data_file = 'data.pklz'
        
        #Try to read cache
        if os.path.isdir(self.folder):
            if os.path.exists(self.folder+'/'+self.data_file):
                with gzip.open(self.folder+'/'+self.data_file, 'rb') as f:
                    self.data = pkl.load(f)
                
        else:
            os.mkdir(self.folder)

        if 'version' not in self.data or self.data['version'] != self.version:
            print('Cache file from an other beampy version!')
            self.data = {}
            self.remove_files()
            
        #check if we the optimize svg option is enabled
        elif 'optimize' not in self.data or self.data['optimize'] != document._optimize_svg:
            print('Reset cache du to optimize')
            self.data = {}
            self.remove_files()
            
        else:
            #Restore glyphs definitions
            if 'glyphs' in self.data:
                document._global_store['glyphs'] = self.data['glyphs']
                
            
            
        #Add beampy version in data
        self.data['version'] = self.version
        self.data['optimize'] = document._optimize_svg
        
    def remove_files(self):
        for f in glob.glob(self.folder+'/*.pklz'):
            os.remove(f)
            
    def clear(self):

        if os.path.isdir(self.folder):
            os.removedirs(self.folder)

        self.data = {}

    def add_to_cache(self, slide, bp_module):
        """
        Add the element of a given slide to the cache data

        slide: str of slide id, exemple: "slide_1"

        bp_module: neampy_module instance
        """

        if bp_module.type not in ['group']:

            #commands that include raw contents (like text, tikz, ...)
            if bp_module.rendered:
                #Set the uniq id from the element['content'] value of the element
                elemid = create_element_id(bp_module, use_args=False, add_slide=False, slide_position=False)
                
                if elemid != None:
                    
                    
                    self.data[elemid] = {}
                    
                    #don't pickle matplotlib figure We don't need to store content in cache
                    #if "matplotlib" not in str(type(bp_module)):
                    #    self.data[elemid]['content'] = bp_module.content
                        
                    self.data[elemid]['width'] = bp_module.positionner.width
                    self.data[elemid]['height'] = bp_module.positionner.height
                    
                    if bp_module.svgout != None:
                        #create a temp filename
                        svgoutname = tempfile.mktemp(prefix='svgout_', dir='')
                        self.data[elemid]['svgout'] = svgoutname
                        #save the file 
                        self.write_file_cache(svgoutname, bp_module.svgout)
                        
                    if bp_module.htmlout != None:
                        htmloutname = tempfile.mktemp(prefix='htmlout_', dir='')
                        self.data[elemid]['htmlout'] = htmloutname
                        self.write_file_cache(htmloutname, bp_module.htmlout)
                        
                    if bp_module.jsout != None:
                        jsoutname = tempfile.mktemp(prefix='jsout_', dir='')
                        self.data[elemid]['jsout'] = jsoutname
                        self.write_file_cache(jsoutname, bp_module.jsout)

                    #print(element['args'])
                    #print(element.keys())
                    #For commands that includes files, need a filename elements in args
                    try:
                        self.data[elemid]['file_id'] = os.path.getmtime( bp_module.content )
                    except:
                        pass



    def is_cached(self, slide, bp_module):
        """
            Function to check if the given element is in the cache or not
        """
        out = False
        #old test on slide  slide in self.data and
        if bp_module.name not in ['group']:
            elemid = create_element_id(bp_module, use_args=False, add_slide=False, slide_position=False)

            #print(bp_module.name,":",elemid)
            if elemid != None and elemid in self.data:
                cacheelem = self.data[elemid]
                out = True

                #Content check OLD TO REMOVE if no bugs
                #the content is now used to generate the elemid 
                #if bp_module.content == cacheelem['content']:
                #    out = True

                #If it's from a file check if the file as changed
                if 'file_id' in cacheelem:
                    try:
                        curtime = os.path.getmtime( bp_module.content )
                    except:
                        curtime = None

                    if curtime != cacheelem['file_id']:
                        out = False
                    else:
                        out = True

                #If It's in cache load items from the cache to the object
                if out:
                    for key in ['svgout', 'jsout', 'htmlout']:
                        if key in cacheelem:
                            content = self.read_file_cache(cacheelem[key])
                            setattr(bp_module, key, content)

                    #Update the size
                    bp_module.update_size(cacheelem['width'], cacheelem['height'])

        return out

    def write_cache(self):
        """
            Export cache data to a pickle file
        """

        """
        for ct in self.data:
            print(ct)
            for elem in self.data[ct]:
                print(elem)
                print(self.data[ct][elem]['element'].keys())
        """

        #Check if their is some glyphs in the global_store
        if 'glyphs' in self.global_store:
            self.data['glyphs'] = self.global_store['glyphs']
            
        with gzip.open(self.folder+'/'+self.data_file, 'wb') as f:
            pkl.dump(self.data, f, protocol=2)
            
            
    def write_file_cache(self, filename, content):
        
        with gzip.open(self.folder+'/'+filename+'.pklz', 'wb') as f:
            f.write(content)

    def read_file_cache(self, filename):
        output = None
        
        with gzip.open(self.folder+'/'+filename+'.pklz', 'rb') as f:
            output = f.read()
            
        return output
        
#TODO: solve import bug when we try to import this function from beampy.functions...
def create_element_id( bp_mod, use_args=True, use_render=True,
                       use_content=True, add_slide=True, slide_position=True,
                       use_size = False ):
    """
        create a unique id for the element using 
        element['content'] and element['args'].keys() and element['render'].__name__
    """
    from beampy.functions import gcs
    from beampy.document import document

    ct_to_hash = ''

    if add_slide:
        ct_to_hash += gcs()

    if use_args and hasattr(bp_mod, 'args'):
        ct_to_hash += ''.join(['%s:%s'%(k,v) for k,v in bp_mod.args.items()])

    if use_render and bp_mod.name != None:
        ct_to_hash += bp_mod.name

    if use_content and bp_mod.content != None:
        ct_to_hash += str(bp_mod.content)

    if use_size:
        if 'height' in bp_mod.args:
            h = bp_mod.args['height']
        else:
            h = 'None'

        if 'width' in bp_mod.args:
            w = bp_mod.args['width']
        else:
            w = 'None'

        ct_to_hash += '(%s,%s)'%(str(w), str(h))

    if slide_position:
        ct_to_hash += str(len(document._slides[gcs()].element_keys))

    if bp_mod.args_for_cache_id != None:
        for key in bp_mod.args_for_cache_id:
            try:
                tmp = getattr(bp_mod, key)
                ct_to_hash += str(tmp)
            except:
                print('No parameters %s for cache id for %s'%(key, bp_mod.name))



    outid = None
    if ct_to_hash != '':
        #print ct_to_hash
        outid = hashlib.md5( ct_to_hash ).hexdigest()

        if outid in document._slides[gcs()].element_keys:
            print("Id for this element already exist!")
            sys.exit(0)
            outid = None
        #print outid

    return outid
