ts=$(date +%s)

aws stepfunctions start-execution --state-machine-arn arn:aws:states:us-east-1:517266833056:stateMachine:counter --input '{"Comment": "Insert your JSON here"}' --region us-east-1 --output json --name $ts
