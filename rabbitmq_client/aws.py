"""s3 module for rabbitmq_client"""

import logging
from typing import Generator, List

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config


def get_s3_object_urls(bucket_name: str, prefix: str = "/", expiration: int = 3600) -> List[str]:
    """Get a list of presigned URLs for the contents of an S3 bucket.

    :param bucket_name: An S3 bucket.
    :type bucket_name: string

    :param prefix: Prefix of files to return. This is S3 for "directory." Defaults to "/", which means all.
    :type object_name: string, optional

    :param expiration: Validity duration for the presigned URL. Defaults to 3600 seconds.
    :type expiration: int, optional

    :return: List containing presigned URLs. If error, returns empty list.
    :rtype: List[str]
    """
    s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name = 'eu-west-2'))
    s3_paginator = s3_client.get_paginator("list_objects_v2")
    urls = []

    def keys(bucket_name: str, prefix: str = "/", delimiter: str = "/") -> Generator[str, None, None]:
        """
        Yields keys contained in an s3 bucket.
        prefix and delimiter follow the formatting of s3 list_objects_v2
        delimiter of "/" makes s3 act like a filesystem, which is our desired behavior.
        """
        prefix = prefix[1:] if prefix.startswith(delimiter) else prefix
        start_after = prefix if prefix.endswith(delimiter) else ""

        for page in s3_paginator.paginate(Bucket=bucket_name, Prefix=prefix, StartAfter=start_after):
            for content in page.get("Contents", ()):
                yield content["Key"]

    for key in keys(bucket_name, prefix):
        try:
            url = s3_client.generate_presigned_url(
                "get_object", Params={"Bucket": bucket_name, "Key": key}, ExpiresIn=expiration
            )
            urls.append(url)
        except ClientError as e:
            logging.error(e)

    return list(urls)
