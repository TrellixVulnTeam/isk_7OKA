###############################################################################
# begin                : Sun Aug  6, 2006  4:58 PM
# copyright            : (C) 2003 by Ricardo Niederberger Cabral
# email                : ricardo dot cabral at imgseek dot net
#
###############################################################################
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
###############################################################################

# standard modules
import sys
import os
import traceback
import time
import logging

# isk modules
from isk import utils

try:
    from isk.imgSeekLib import imgdb
except:
    logging.error("""Unable to load the C++ extension \"_imgdb.so(pyd)\" module.""")
    logging.error("""See http://www.imgseek.net/isk-daemon/documents-1/compiling""")
    traceback.print_exc()
    sys.exit()

log = logging.getLogger('imageDB')

SUPPORTED_IMG_EXTS = [ 'jpeg', 'jpg', 'gif', 'png', 'rgb', 'jpe', 'pbm', 'pgm', 'ppm', 'tiff', 'tif', 'rast', 'xbm', 'bmp' ] # to help determining img format from extension

def safe_str(obj):
    """ return the byte string representation of obj """
    return str(obj)
    # try:
    #     return str(obj)
    # except UnicodeEncodeError:
    #     # obj is unicode
    #     return unicode(obj).encode('unicode_escape')

def addCount(dbSpace):
    # add per minutes counting
    dbSpace.addCount += 1
    if time.localtime()[4] > dbSpace.addMinCur:
        dbSpace.addMinCur = time.localtime()[4]
        dbSpace.lastAddPerMin = dbSpace.addMinCount
    else:
        dbSpace.addMinCount += 1

def countQuery(dbSpace):
    dbSpace.queryCount += 1
    if time.localtime()[4] > dbSpace.queryMinCur:
        dbSpace.queryMinCur = time.localtime()[4]
        dbSpace.lastQueryPerMin = dbSpace.queryMinCount
    else:
        dbSpace.queryMinCount += 1

def normalizeResults(results):
    """ normalize results returned by imgdb """

    res = []
    for i in range(int(len(results) / 2)):
        rid = results[i*2]
        rsc = results[i*2+1]
        rsc = -100.0*rsc/38.70  # normalize #TODO is this normalization factor still valid?
        #sanity checks
        if rsc<0:rsc = 0.0
        if rsc>100:rsc = 100.0
        res.append([rid,rsc])
        
    res.reverse()
    return res

class DBSpace:
    def __init__(self, id):
        # statistics
        self.id = id
        self.queryCount = 0
        self.lastQueryPerMin = 0
        self.queryMinCount = 0
        self.queryMinCur = 0
        self.lastAddPerMin = 0
        self.addMinCount = 0
        self.addMinCur = 0
        self.addCount = 0        
        self.addSinceLastSave = 0                
        self.lastId = 1                
        self.lastSaveTime = 0
        self.fileName = 'not yet saved' # currently loaded data file
        
        if not imgdb.isValidDB(id): # only init if needed
            log.debug("New dbSpace requires init: %d"%id)
            imgdb.initDbase(id)
        
    def __str__(self):
        reprs = "DPSpace ; "
        for key in dir(self):
            if not key.startswith('__'):
                value = getattr(self,key)
                if not callable(value):
                    reprs += key + "=" + str(value) + "; "
        return reprs
        
    """
    #TODO not refactoring all ImgDB fcns into here in order to save some function calls
    So this class is in a sense a mere data structure.

    def postLoad(self):
        # adjust last added image id
        self.lastId = self._imgdb.getImageCount(self.id) + 1        
        log.info('Database loaded: ' + self)
    """

#TODO apply memoizing (see utils) to some methods ?
class ImgDB:   
    def __init__(self, settings):
        self.db_spaces = {}
        self.globalFileName = 'global-imgdb-not-saved-yet'
        # global statistics
        self._settings = settings     
            
    @utils.dump_args
    def createdb(self, db_id):
        if db_id in self.db_spaces:
            log.warn('Replacing existing database id: %s', str(db_id))
        self.db_spaces[db_id] = DBSpace(db_id)
        self.resetdb(db_id)
        return db_id

    @utils.dump_args
    def closedb(self):
        return imgdb.closeDbase()
        
    @utils.require_known_db_id
    @utils.dump_args
    def resetdb(self, dbId):
        if imgdb.resetdb(dbId): # succeeded
            self.db_spaces[dbId] = DBSpace(dbId)
            log.debug("resetdb() ok")            
            return 1
        return 0

    @utils.dump_args
    def loaddb(self, dbId, fname):
        if imgdb.resetdb(dbId):
            log.warn('Load is replacing existing database id:'+str(dbId))
        dbSpace = DBSpace(dbId)
        self.db_spaces[dbId] = dbSpace
        dbSpace.fileName = fname
        
        if not imgdb.loaddb(dbId, fname):
            log.error("Error loading image database")
            del self.db_spaces[dbId]
            return None
        # adjust last added image id
        log.info('| Database loaded: ' + str(dbSpace))
        dbSpace.lastId = self.getImgCount(dbSpace.id) + 1
        return dbId

    @utils.require_known_db_id
    @utils.dump_args
    def savedb(self,dbId):        
        return imgdb.savedb(dbId, self.db_spaces[dbId].fileName)
            
    @utils.require_known_db_id
    @utils.dump_args
    def savedbas(self,dbId,fname):        
        if not imgdb.savedb(dbId, fname):
            log.error("Error saving image database")
            return 0
        else:
            dbSpace = self.db_spaces[dbId]
            dbSpace.lastSaveTime = time.time()
            dbSpace.fileName = fname
            log.info('| Database id=%s saved to "%s"' % ( dbSpace, fname))
            return 1
        
    @utils.dump_args
    def loadalldbs(self, fname):
        try:
            dbCount = imgdb.loadalldbs(fname)
            for dbid in self.getDBList():
                self.db_spaces[dbid] = DBSpace(dbid)
                self.db_spaces[dbid].lastId = self.getImgCount(dbid) + 1
            log.debug('| Database (%s) loaded with %d spaces' %(fname, dbCount))
            self.globalFileName = fname
            return dbCount            
        except RuntimeError as e:
            log.error(e)
            return 0

    @utils.dump_args
    def savealldbs(self, fname=None):
        if not fname:
            fname = self.globalFileName
        res = imgdb.savealldbs(fname)
        if not res:
            log.error("Error saving image database")
            return res
        log.info('| All database spaces saved at "%s"' % fname)
        return res
            
    @utils.require_known_db_id
    @utils.dump_args
    def addDir(self, dbId, path, recurse, fname_as_id=False):
        
        path = safe_str(path)        
        
        addedCount = 0
        dbSpace = self.db_spaces[dbId]
        if not os.path.isdir(path):
            log.error("'%s' does not exist or is not a directory" % path)
            return 0
        for fil in os.listdir(path):
            fil = safe_str(fil)
            fil = path + os.sep + fil 
            if len(fil) > 4 and fil.split('.')[-1].lower() in SUPPORTED_IMG_EXTS:
                file_name = os.path.splitext(os.path.basename(fil))[0]
                image_id = dbSpace.lastId

                # If ``fname_as_id`` is True, try to retrieve image id from filename.
                if fname_as_id:
                    try:
                        image_id = int(file_name)
                    except ValueError:
                        log.error("Can not get id from filename {}. Skipping".format(file_name))
                        continue

                # Add image to db
                try:
                    addedCount += self.addImage(dbId, fil, image_id)
                except RuntimeError as e:
                    log.error(e)

            elif recurse and os.path.isdir(fil):
                addedCount += self.addDir(dbId, fil, recurse, fname_as_id)
        return addedCount        

    @utils.require_known_db_id
    @utils.dump_args
    def removeDb(self, dbId):
        if imgdb.removedb(dbId):
            del self.db_spaces[dbId]
            return True
        return False

    @utils.require_known_db_id
    @utils.dump_args
    def addImageBlob(self, dbId, data, newid = None):
        dbSpace = self.db_spaces[dbId]
        
        if not newid:
            newid = dbSpace.lastId
            
        newid = newid
        addCount(dbSpace)
        # call imgdb
        res = imgdb.addImageBlob(dbId, newid, data)

        if res != 0: # add successful
            dbSpace.lastId = newid + 1
            # time to save automatically ?            
            #TODO this should be a reactor timer
            if self._settings.core.getboolean('database','automaticSave') and \
               time.time() - dbSpace.lastSaveTime > self._settings.core.getint('database','saveInterval'):
                dbSpace.lastSaveTime = time.time()
                self.savealldbs()
        return res

    @utils.require_known_db_id
    @utils.dump_args
    def addImage(self, dbId, fname,newid = None):
        dbSpace = self.db_spaces[dbId]
        
        if not newid:
            newid = dbSpace.lastId
            
        newid = newid
        addCount(dbSpace)
       # call imgdb
        res = imgdb.addImage(dbId, newid, fname)

        if res != 0: # add successful
            dbSpace.lastId = newid + 1
            # time to save automatically ?            
            if self._settings.core.getboolean('database','automaticSave') and \
               time.time() - dbSpace.lastSaveTime > self._settings.core.getint('database','saveInterval'):
                dbSpace.lastSaveTime = time.time()
                self.savealldbs()
        return res

    @utils.require_known_db_id
    @utils.dump_args
    def removeImg(self,dbId,id):
        #TODO should also call the code that saves db after a number of ops
        #id = long(id)        
        return imgdb.removeID(dbId,id)

    def getDBDetailedList(self):
        dbids = self.getDBList()
        detlist = {}
        for id in dbids:
            dbSpace = self.db_spaces[id]
            detlist[str(id)]= [
                            self.getImgCount(id),
                            dbSpace.queryCount,
                            dbSpace.lastQueryPerMin,
                            dbSpace.queryMinCount,
                            dbSpace.queryMinCur,
                            dbSpace.lastAddPerMin,
                            dbSpace.addMinCount,
                            dbSpace.addMinCur,
                            dbSpace.addCount,
                            dbSpace.addSinceLastSave,
                            dbSpace.lastId,
                            dbSpace.lastSaveTime,
                            dbSpace.fileName,
                            ]
        return detlist

    @utils.require_known_db_id
    def isImageOnDB(self,dbId,id):
        return imgdb.isImageOnDB(dbId,id)

    @utils.require_known_db_id
    def calcAvglDiff(self,dbId,id1,id2):
        return imgdb.calcAvglDiff(dbId, id1,id2)

    @utils.require_known_db_id
    def calcDiff(self,dbId,id1,id2):
        return imgdb.calcDiff(dbId, id1,id2)

    @utils.require_known_db_id
    def getImageDimensions(self,dbId,id):
        return [imgdb.getImageWidth(dbId,id),imgdb.getImageHeight(dbId,id)]

    @utils.require_known_db_id
    def getImageAvgl(self,dbId,id):
        return imgdb.getImageAvgl(dbId,id)

    @utils.require_known_db_id
    def getIdsBloomFilter(self,dbId):
        return imgdb.getIdsBloomFilter(dbId)

    @utils.require_known_db_id
    def getImgCount(self, dbId):
        return imgdb.getImgCount(dbId)

    @utils.require_known_db_id
    def getImgIdList(self,dbId):
        return imgdb.getImgIdList(dbId)
    
    def isValidDB(self,dbId):
        return imgdb.isValidDB(dbId)

    def getDBList(self):
        return imgdb.getDBList()
    
    @utils.require_known_db_id
    def getQueryCount(self,dbId):
        return self.db_spaces[dbId].queryCount

    @utils.require_known_db_id
    def getQueryPerMinCount(self,dbId):
        return self.db_spaces[dbId].lastQueryPerMin

    @utils.require_known_db_id
    def getAddCount(self,dbId):
        return self.db_spaces[dbId].addCount

    @utils.require_known_db_id
    def getAddPerMinCount(self,dbId):
        return self.db_spaces[dbId].lastAddPerMin

    @utils.require_known_db_id
    @utils.dump_args
    def addKeywordImg(self, dbId, imgId, hash):
        return imgdb.addKeywordImg(dbId, imgId, hash)

    @utils.require_known_db_id
    def getClusterKeywords(self,dbId, numClusters,keywords):
        return imgdb.getClusterKeywords(dbId, numClusters,keywords)
    
    @utils.require_known_db_id
    def getClusterDb(self,dbId, numClusters):
        return imgdb.getClusterDb(dbId, numClusters)
    
    @utils.require_known_db_id
    def getKeywordsPopular(self,dbId, numres):
        return imgdb.getKeywordsPopular(dbId, numres)
    
    @utils.require_known_db_id
    def getKeywordsVisualDistance(self,dbId, distanceType,  keywords):
        return imgdb.getKeywordsVisualDistance(dbId, distanceType,  keywords)
    
    @utils.require_known_db_id
    def getAllImgsByKeywords(self,dbId, numres, kwJoinType, keywords):
        return imgdb.getAllImgsByKeywords(dbId, numres, kwJoinType, keywords)
    
    @utils.require_known_db_id
    def queryImgIDFastKeywords(self,dbId, imgId, numres, kwJoinType, keywords):
        return imgdb.queryImgIDFastKeywords(dbId, imgId, numres, kwJoinType, keywords)

    @utils.require_known_db_id
    def queryImgIDKeywords(self,dbId, imgId, numres, kwJoinType, keywords, fast=False):
        dbSpace = self.db_spaces[dbId]
        
        # return [[resId,resRatio]]
        # update internal counters
        numres = int(numres) + 1
        countQuery(dbSpace)

        # do query
        results = imgdb.queryImgIDKeywords(dbId, imgId, numres, kwJoinType, keywords,fast)            

        res = normalizeResults(results)

        log.debug("queryImgIDKeywords() ret="+str(res))
        return res

    @utils.require_known_db_id
    def mostPopularKeywords(self,dbId, imgs, excludedKwds, count, mode):
        res = imgdb.mostPopularKeywords(dbId, imgs, excludedKwds, count, mode)        
        log.debug("mostPopularKeywords() ret="+str(res))
        return res

    @utils.require_known_db_id
    def getKeywordsImg(self,dbId, imgId):
        res = imgdb.getKeywordsImg(dbId, imgId)
        log.debug("getKeywordsImg() ret="+str(res))
        return res
    
    @utils.require_known_db_id
    @utils.dump_args
    def removeAllKeywordImg(self, dbId, imgId):
        return imgdb.removeAllKeywordImg(dbId, imgId)
    
    @utils.require_known_db_id
    @utils.dump_args
    def removeKeywordImg(self,dbId, imgId, hash):
        return imgdb.removeKeywordImg(dbId, imgId, hash)
    
    @utils.require_known_db_id
    @utils.dump_args
    def addKeywordsImg(self,dbId, imgId, hashes):
        return imgdb.addKeywordsImg(dbId, imgId, hashes)

    @utils.require_known_db_id
    def queryImgBlob(self,dbId,data,numres,sketch=0,fast = False):
        dbSpace = self.db_spaces[dbId]
        
        # return [[resId,resRatio]]
        # update internal counters
        numres = int(numres) + 1
        countQuery(dbSpace)
        # do query
        results = imgdb.queryImgBlob(dbId,data,numres,sketch,fast)

        res = normalizeResults(results)

        log.debug("queryImgBlob() ret="+str(res))        
        return res

    @utils.require_known_db_id
    @utils.dump_args
    def queryImgPath(self,dbId,path,numres,sketch=0, fast = False):
        dbSpace = self.db_spaces[dbId]
        
        # return [[resId,resRatio]]
        # update internal counters
        numres = int(numres) + 1
        countQuery(dbSpace)
        # do query
        results = imgdb.queryImgPath(dbId,path,numres,sketch, fast)

        res = normalizeResults(results)

        log.debug("queryImgPath() ret="+str(res))        
        return res    
    
    @utils.require_known_db_id
    @utils.dump_args
    def queryImgID(self,dbId,qid,numres,sketch=0,fast = False):
        dbSpace = self.db_spaces[dbId]
        
        # return [[resId,resRatio]]
        # update internal counters
        numres = int(numres) + 1
        countQuery(dbSpace)
        # do query
        results = imgdb.queryImgID(dbId,qid,numres,sketch, fast)

        res = normalizeResults(results)

        log.debug("queryImgID() ret="+str(res))        
        return res
