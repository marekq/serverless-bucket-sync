#!/usr/bin/python
# marek kuczynski
# @marekq
# www.marek.rocks
# coding: utf-8

# import neccesary libraries
import botocore, boto3, threading, time, os, queue

# create the neccesary boto3 client and resource connections
s3r     = boto3.resource('s3', config = botocore.client.Config(max_pool_connections = 100))
s3c     = boto3.client('s3', config = botocore.client.Config(max_pool_connections = 100))
ec2     = boto3.client('ec2')
buckn   = os.environ['source_bucket']

q1      = queue.Queue()
q2      = queue.Queue()

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

# worker for queue jobs that retrieves a list of S3 files in a bucket.
def worker_list():
    while not q2.empty():
        x   = q2.get()
        get_reg_bucket(x)
        q2.task_done()

# get an overview of all AWS regions.
def get_regions():
    c       = []
    resp    = ec2.describe_regions()
    for x in resp['Regions']:
        c.append(x['RegionName'])
        
    return c

# get a list of all S3 buckets meeting the naming convention (i.e. s3://marek-serverless-<region-name>)
def get_buckets():
    c           = []
    my_buckets  = s3r.buckets.all()
    for bucket in my_buckets:
        if buckn+'-' in bucket.name and bucket.name != buckn:
            c.append(bucket.name)
    
    return c

# get all files within a given S3 bucket. 
def get_files(b):
    indx        = {}
    objs        = s3c.list_objects_v2(Bucket = b)
    
    if objs['KeyCount'] != 0:
        for obj in objs['Contents']:
            indx[obj['Key']] = obj['ETag']

    return indx

# create an S3 bucket with ACL permissions of your choice. 
def create_bucket(reg, acl):        
    sess    = boto3.session.Session()
    s3b     = sess.client('s3', region_name = reg)

    if reg != 'us-east-1':
        s3b.create_bucket(ACL = acl, Bucket = buckn+'-'+reg, CreateBucketConfiguration = {'LocationConstraint': reg})

    else:
        s3b.create_bucket(ACL = acl, Bucket = buckn+'-'+reg)

    print('creating bucket '+buckn+'-'+reg+' with acl '+acl)

# checks whether a bucket was created in every AWS region. if a bucket is missing, it will be automatically created. 
def create_replication_buckets(aws_reg, s3_reg, acl):
    new_buck    = False
    buck_reg    = []
    
    for path in s3_reg:
        reg     = '-'.join(path.split('-')[-3:])
        buck_reg.append(reg)
        
    for reg in aws_reg:
        if reg not in buck_reg:
            create_bucket(reg, acl)
            new_buck    = True
     
    # if a bucket was created, rerun the s3 bucket overview.
    if new_buck:
        return get_buckets()
        
    else:
        return s3_reg

# copy an object from the source to the destination bucket.
def copy_obj(buck, item):
    src     = {'Bucket' : buckn, 'Key': item}
    s3r.Object(buck, item).copy(src)
    print('copied '+item+' to '+buck)

# delete a given object from an s3 bucket. 
def delete_obj(buck, item):
    s3r.Object(buck, item).delete()
    print('delete '+item+' in '+buck)

# check whether any files need to be copied or deleted by comparing objects in the source bucket. 
def get_reg_bucket(buck):
    s3_indx     = get_files(buck)
        
    # check whether any files are missing in the destination buckets and copies them if needed. 
    for item, etag in src_indx.items():
        if item not in s3_indx.keys():
            q1.put(['copy', buck, item])

        if etag not in s3_indx.values():
            q1.put(['copy', buck, item])

    # check whether any unneccesary files are present in the destination buckets and deletes them if needed.        
    for item, etag in s3_indx.items():
        if item not in src_indx.keys():
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
    global src_indx
    
    # get the files in the source bucket which will be replicated and the destination buckets.  
    src_indx    = get_files(buckn)
    
    # check which buckets are present in the account with the correct naming convention ( "s3://<source-bucket>-eu-west-1/" for example).
    s3_reg      = get_buckets()
    
    # check which AWS regions are available to create a bucket in (excluding the gov clouds and china regions).
    aws_reg     = get_regions()
    
    # check the acl of the source bucket for whether it allows public s3 access or not. 
    acl         = get_buck_acl(buckn)
    
    # if required, create any missing replication buckets (i.e. because a new region became available or a bucket was deleted).
    s3_reg      = create_replication_buckets(aws_reg, s3_reg, acl)

    # check the contents of every existing replication bucket using 20 threads.
    for buck in s3_reg:
        q2.put(buck)

    bf          = str(q2.qsize())

    for x in range(20):
        t           = threading.Thread(target = worker_list)
        t.daemon    = True
        t.start()
    q2.join()    

    # copy or delete any objects that are different from the source bucket using 100 threads.
    startt          = int(round(time.time() * 100))
    ops             = str(q1.qsize())

    for x in range(100):
        t           = threading.Thread(target = worker_crud)
        t.daemon    = True
        t.start()
    q1.join()
    
    stopt           = int(round(time.time() * 100))
    
    # print how many buckets were found, how long the copy operations took and how many operations were done per second. 
    print(bf+' \t buckets found') 
    print(ops+' \t operations to copy/delete objects')
    print(float(ops * 100) / float(stopt - startt), ' \t operations per second')
    
    # return an overview of created/deleted/skipped items for diagnostic purposes. 
    return bf+' buckets found, '+ops+' copy/delete operations'

