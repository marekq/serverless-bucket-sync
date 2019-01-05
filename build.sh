ts=$(date +%s)

zip -u9qr sbs.zip *
aws s3 cp sbs.zip s3://marek-serverless/ --acl public-read

echo 'creating new cfn stack sbs-'$ts
aws cloudformation deploy --template-file ./template.yml --parameter-overrides SourceBucket=marek-serverless --capabilities CAPABILITY_IAM --region us-east-1 --stack-name sbs-$ts
