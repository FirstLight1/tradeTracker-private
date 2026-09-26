import boto3
import os
from botocore.exceptions import ClientError
from io import BytesIO

class R2Service:
    def __init__(self):
        self.r2 = boto3.client(
                service_name='s3',
                endpoint_url=os.environ.get('R2_ENDPOINT'),
                aws_access_key_id=os.environ.get('R2_KEY_ID'),
                aws_secret_access_key=os.environ.get('R2_API_KEY'),
                region_name='auto', 
                )

    def upload_file(self, file: bytes, file_name: str, bucket_name: str) -> None:
        if file_name is None:
            raise Exception("File name is required")
        if file is None:
            raise Exception("File is required")

        try:
            self.r2.put_object(Body=file, Bucket=bucket_name, Key=file_name)
        except ClientError as e:
            raise Exception(f"Failed to upload file to R2: {e}")


    def download_file(self, file_name, bucket_name: str) -> BytesIO:
        file = BytesIO()
        self.r2.download_object(bucket_name, file_name, file)
        file.seek(0)
        return file

