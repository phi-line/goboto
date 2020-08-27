import os
import logging

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv('AWS_DEFAULT_REGION')
S3_BUCKET = os.getenv('S3_BUCKET')
S3_BUCKET_URL = f'https://s3-{AWS_REGION}.amazonaws.com/{S3_BUCKET}'

def upload_file(full_path):
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(
            full_path,
            S3_BUCKET,
            full_path,
            ExtraArgs={'ACL': 'public-read'}
        )
        return f'{S3_BUCKET_URL}/{full_path}'
    except ClientError as e:
        logging.error(e)
        return False

def flush_directory(directory):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(S3_BUCKET)
    bucket.objects.filter(Prefix=directory).delete()
