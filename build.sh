zip -r sbs.zip *
aws s3 cp sbs.zip s3://marek-serverless/ --acl public-read