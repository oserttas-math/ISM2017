# -*- coding: utf-8 -*-
#!/usr/bin/python
#
# Author    Yann Bayle
# E-mail    bayle.yann@live.fr
# License   MIT
# Created   30/03/2017
# Updated   30/03/2017
# Version   1.0.0
#

"""
Description of recisio.py
======================


:Example:

source activate py27
python recisio.py

"""

import os
import re
import sys
import utils
import shutil
import pymysql

def rm_space(string):
    """
    remove the first and last space if present in the str
    """
    if " " in string[0]:
        string = string[1:]
    if " " in string[-1]:
        string = string[:-1]
    return string

def list_files():
    folders = ["../features/marsyas/", "../features/yaafe/"]
    data = []
    for fold in folders:
        file_list = os.listdir(fold)
        for filen in file_list:
            filen = filen.replace("_", " ")
            info = filen.split("-")
            data.append(rm_space(info[2]) + "," + rm_space(info[0]) + "," + rm_space(info[1]) + "\n")
    data = list(set(data))
    with open("file_list.csv", "w") as filep:
        filep.write("id,artist,track\n")
        for line in data:
            filep.write(line)

def yaafe(filen):
    # Assert Python version
    if sys.version_info.major != 2:
        utils.print_error("Yaafe needs Python 2 environment")
    
    dir_tracks = filen.split("/")
    old_fn = dir_tracks[-1]
    dir_tracks = os.sep.join(dir_tracks[:-1]) + "/"
    new_fn = old_fn.replace("'", "_")
    new_fn = new_fn.replace('"', "_")
    print(dir_tracks)
    os.rename(dir_tracks + old_fn, dir_tracks + new_fn)
    filen = "'" + new_fn + "'"
    print(filen)
    dir_feat = utils.create_dir(utils.create_dir("../features/") + "yaafe/")
    dir_current = os.getcwd()
    os.chdir(dir_tracks)
    yaafe_cmd = 'yaafe -r 22050 -f "mfcc: MFCC blockSize=2048 stepSize=1024" '
    yaafe_cmd += "--resample -b " + dir_feat + " "
    os.system(yaafe_cmd + filen)
    # os.system(yaafe_cmd + filen + " > /dev/null 2>&1")
    os.chdir(dir_current)

def bextract_features(in_fn, out_fn, verbose=False):
    bextract_cmd = "bextract -mfcc -zcrs -ctd -rlf -flx -ws 1024 -as 898 -sv -fe " + in_fn + " -w " + out_fn
    if not verbose:
        bextract_cmd += " > /dev/null 2>&1"
    os.system(bextract_cmd)

def validate_arff(filename):
    """Description of validate_arff

    Check if filename exists on path and is a file
    If file corresponds to valid arff file return absolute path
    Otherwise move file to invalid directory and return False
    """
    # Check if file exists
    if os.path.isfile(filename) and os.path.exists(filename):
        filename = os.path.abspath(filename)
    else:
        return False
    # If does not satisfy min size, move to "empty" folder
    if os.stat(filename).st_size < 8100:
        tmp_path = filename.split("/")
        empty_dirname = "/".join(tmp_path[:-1]) + "/empty/"
        if not os.path.exists(empty_dirname):
            os.makedirs(empty_dirname)
        shutil.move(filename, empty_dirname + tmp_path[-1])
        return False
    # # If filename does not match with feature name, move to "invalid" folder
    # name_file = filename.split("/")[-1][:12]
    # with open(filename) as filep:
    #     for i, line in enumerate(filep):
    #         if i == 70:
    #             # 71th line
    #             name_feat = line.split(" ")[2][1:13]
    #             break
    # if name_file != name_feat:
    #     tmp_path = filename.split("/")
    #     invalid_dirname = "/".join(tmp_path[:-1]) + "/invalid/"
    #     if not os.path.exists(invalid_dirname):
    #         os.makedirs(invalid_dirname)
    #     shutil.move(filename, invalid_dirname + tmp_path[-1])
    #     return False
    # If everything went well, return filename absolute path
    return filename

def merge_arff(indir, outfilename):
    """Description of merge_arff

    bextract program from Marsyas generate one output file per audio file
    This function merge them all in one unique file
    Check if analysed file are valid i.e. not empty
    """
    utils.print_success("Preprocessing ARFFs")
    indir = utils.abs_path_dir(indir)
    filenames = os.listdir(indir)
    outfn = open(outfilename, 'w')
    cpt_invalid_fn = 0
    # Write first lines of ARFF template file
    for filename in filenames:
        if os.path.isfile(indir + filename):
            new_fn = validate_arff(indir + filename)
            if new_fn:
                with open(new_fn, 'r') as template:
                    nb_line = 74
                    for line in template:
                        if not nb_line:
                            break
                        nb_line -= 1
                        outfn.write(line)
                    break
            else:
                cpt_invalid_fn += 1
    # Append all arff file to the output file
    cur_file_num = 1
    for filename in filenames:
        if os.path.isfile(indir + filename):
            new_fn = validate_arff(indir + filename)
            if new_fn:
                cur_file_num = cur_file_num + 1
                utils.print_progress_start("Analysing file\t" + str(cur_file_num))
                fname = open(new_fn, 'r')
                outfn.write("".join(fname.readlines()[74:77]))
                fname.close()
            else:
                cpt_invalid_fn += 1
    utils.print_progress_end()
    outfn.close()
    # os.system("rm " + indir + "*.arff")
    if cpt_invalid_fn:
        utils.print_warning(str(cpt_invalid_fn) + " ARFF files with errors found")
    return outfilename

def marsyas(out_dir, filelist):
    """Definition of marsyas

    bextract is the cmd in marsyas that extract the features.
    It needs as input a file which contains a list of audio files to compute.
    If an audio file is corrupted, bextract crashes.
    So, it is necessary to call bextract with only one audio file each time. 

    bextract then produces one output file for each audio file.
    It is neccesary to merge those files into one common file.
    """
    dir_feat = utils.create_dir(utils.create_dir(out_dir) + "marsyas/")
    tmp = "tmp.mf"
    for index, filen in enumerate(filelist):
        utils.print_progress_start(str(index+1) + "/" + str(len(filelist)) + " " + filen.split(os.sep)[-1])
        with open(tmp, "w") as filep:
            filep.write(filen + "\n")
        filen = filen.split("/")[-1]
        filen = filen.replace(" ", "_")
        filen = filen.replace("'", "_")
        filen = filen.replace('"', "_")
        outfilename = dir_feat + filen + ".arff"
        bextract_features(tmp, outfilename)
    merge_arff(dir_feat, out_dir + "marsyas.arff")

def run_cmd(cmd, verbose=False):
    if not verbose:
        cmd += " > /dev/null 2>&1"
    os.system(cmd)

def essentia_extract_feat(in_fn, out_fn, verbose=False):
    cmd = "/home/yann/MTG/Extractor/essentia-extractors-v2.1_beta2/streaming_extractor_music '" + in_fn + "' '" + out_fn + "'"
    run_cmd(cmd)

def essentia(out_dir, filen):
    dir_feat = utils.create_dir(utils.create_dir(out_dir) + "essentia/")
    output = dir_feat + filen.split("/")[-1] + ".json"
    essentia_extract_feat(filen, output)

def extract_features(dir_feat):
    filelist = []
    folder = "/media/sf_SharedFolder/DataSets/Recisio/audio/"
    for fold in os.listdir(folder):
        for filename in os.listdir(folder + fold):
            if "ld.wav" in filename:
                filelist.append(folder + fold + "/" + filename)
    # marsyas(dir_feat, filelist)
    for index, filen in enumerate(filelist):
        utils.print_progress_start(str(index+1) + "/" + str(len(filelist)) + " " + filen.split(os.sep)[-1])
        # yaafe(filen)
        essentia(dir_feat, filen)
    utils.print_progress_end()


def request(query, verbose=False):
    try:
        db = pymysql.connect(host="localhost",user="yann",passwd="yann",db="doctorat")
    except Exception:
        print("Error in MySQL connexion")
    else:
        cur = db.cursor()
        try:
            cur.execute(query)
        except Exception:
            print("Error with query: " + query)
        else:
            db.commit()
            result = cur.fetchall()
            print(result)
        db.close()

def update_filelist():
    """
    @brief      Update the database with the boolean indicating if features have
     been extracted a tool
    """
    main_dir = "E:/_These/DataSets/Recisio/features/"
    folders = ["marsyas/", "yaafe/", "essentia/"]
    data = []
    for fold in folders:
        fold = main_dir + fold
        query = "UPDATE recisio SET " + fold.split("/")[-2] + " = 1 WHERE id = "
        file_list = os.listdir(fold)
        for index, filen in enumerate(file_list):
            print(index)
            m = re.search(r"\d{2,10}", filen)
            request(query + m.group())

def export(outfile):
    """
    @brief      Export artist and track name from the database
    @param      outfile  The outfile for storing artist and track name
    """
    query = "SELECT artist,track FROM recisio WHERE marsyas=1 AND yaafe=1 and essentia=1 "
    query += "ORDER BY artist ASC "
    query += "INTO OUTFILE '" + outfile + "' "
    query += "FIELDS TERMINATED BY ',' "
    request(query)

def main():
    """
    @brief      Main entry point
    """
    # list_files()
    # update_filelist()
    export(outfile="D:/_Doctorat/ISMIR2017/data/artist_track.csv")
    # extract_features(dir_feat="../features/")

if __name__ == "__main__":
    main()