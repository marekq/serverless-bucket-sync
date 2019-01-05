import boto3, json

def get_regions():
    ec2 	= boto3.client('ec2')
    c       = []
    resp    = ec2.describe_regions()
    for x in resp['Regions']:
        c.append(x['RegionName'])
        
    return sorted(c)

def gen_state_machine(reg):
	x 	= '{"StartAt": "'+reg+'", "States": { "'+reg+'": { "Type": "Task", "Resource": "${lambdaArn}", "ResultPath": "$", "End": true, "Parameters": { "region": "'+reg+'"}}}},'
	return x

reg 	= get_regions()
start = '{"Comment": "Serverless Bucket Sync", "StartAt": "Parallel", "States": {"Parallel": {"Type": "Parallel", "Next": "Final", "Branches": ['
final = ']}, "Final": {"Type": "Pass", "End": true}}}'

ret 	= ''
ret 	+= start

mid   = ''
for r in reg:
	mid += gen_state_machine(r)

ret   += mid[:-1]
ret 	+= final

obj   = json.loads(str(ret))
fin   = json.dumps(obj, indent = 1, sort_keys = True)

f 		= open('stepfunction.json', 'wb')
f.write(fin+'\r')
f.close()
