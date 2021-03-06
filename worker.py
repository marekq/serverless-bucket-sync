#!/usr/bin/python
# marek kuczynski
# @marekq
# www.marek.rocks
# coding: utf-8

# import neccesary libraries
import botocore, boto3, threading, time, os, queue

# create the neccesary boto3 client and resource connections
s3r     = boto3.resource('s3', config = botocore.client.Config(max_pool_connections = 20))
s3c     = boto3.client('s3', config = botocore.client.Config(max_pool_connections = 20))
ec2     = boto3.client('ec2')
q1      = queue.Queue()

##########

# worker for queue jobs that copy/delete files
def worker_crud():
    while not q1.empty():
        x       = q1.get()
        
        if x[0] == 'copy':
            copy_obj(x[1], x[2])
            
        elif x[0] == 'delete':
            delete_obj(x[1], x[2])
            
        q1.task_done()

# get all files within a given S3 bucket. 
def get_files(buck):
    index       = {}
    objs        = s3c.list_objects_v2(Bucket = buck)
    
    if objs['KeyCount'] != 0:
        for obj in objs['Contents']:
            index[obj['Key']] = obj['ETag']

    return index

# copy an object from the source to the destination bucket.
def copy_obj(buck, item):
    src     = {'Bucket' : srcbuck, 'Key': item}
    s3r.Object(buck, item).copy(src)
    print('copied '+item+' to '+buck)

# delete a given object from an s3 bucket. 
def delete_obj(buck, item):
    s3r.Object(buck, item).delete()
    print('delete '+item+' in '+buck)

# check whether any files need to be copied or deleted by comparing objects in the source bucket. 
def get_reg_bucket(buck, src_index, dst_index):  

    # check whether any files are missing in the destination buckets and copies them if needed. 
    for item, etag in src_index.items():
        if item not in dst_index.keys():
            q1.put(['copy', buck, item])

        if etag not in dst_index.values():
            q1.put(['copy', buck, item])

    # check whether any unneccesary files are present in the destination buckets and deletes them if needed.        
    for item, etag in dst_index.items():
        if item not in src_index.keys():
            q1.put(['delete', buck, item])

# checks whether the bucket has a public or private acl and return the acl. 
def get_buck_acl(b):
    y       = ''
    try:
        x   = s3c.get_bucket_policy_status(Bucket = b)

        if x['PolicyStatus']['IsPublic'] == 'True':
            y   = 'public-read'
    
        elif x['PolicyStatus']['IsPublic'] == 'False':
            y   = 'private'

    except Exception as e:
        y       = 'private'

    return y

# the lambda handler bootstrapping the code.
def handler(event, context):
    global srcbuck
    srcbuck         = os.environ['source_bucket']
    dstbuck         = srcbuck+'-'+event['region']

    src_index       = get_files(srcbuck)
    dst_index       = get_files(dstbuck)
    get_reg_bucket(dstbuck, src_index, dst_index)

    # copy or delete any objects that are different from the source bucket using 100 threads.
    startt          = int(round(time.time() * 100))
    ops             = str(q1.qsize())

    for x in range(20):
        t           = threading.Thread(target = worker_crud)
        t.daemon    = True
        t.start()
    q1.join()
    
    stopt           = int(round(time.time() * 100))
    
    # print how many buckets were found, how long the copy operations took and how many operations were done per second. 
    print(ops+' operations to copy/delete objects')
    print(float(ops * 100) / float(stopt - startt), ' operations per second')
    
    # return an overview of created/deleted/skipped items for diagnostic purposes. 
    return 'sync from '+srcbuck+' to '+dstbuck+', '+ops+' copy/delete operations'
