from qcloud_cos import CosConfig, CosS3Client
import os
import Utils.config

from Utils.color_logger import get_logger
logger = get_logger(__name__)

root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config_dir = os.path.join(root_dir, "Config")
config_fp = os.path.join(config_dir, 'cos_config.json')


# 目前使用腾讯的对象存储服务
# https://cloud.tencent.com/document/product/436/12269
class COS:
    __global_config = Utils.config.COSConfig(config_fp)
    __cos_config: CosConfig = None
    __client: CosS3Client = None

    def __init__(self):
        """
        :param secret_id: 临时密钥的 SecretId，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
        :param secret_key:临时密钥的 SecretKey，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
        :param region:替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
        :param token:临时密钥的 Token，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
        :param scheme:指定使用 http/https 协议来访问 COS，默认为 https，可不填
        """
        COS.__cos_config = CosConfig(Region=COS.__global_config.region,
                                     SecretId=COS.__global_config.secret_id,
                                     SecretKey=COS.__global_config.secret_key,
                                     Token=None,
                                     Scheme="https")
        COS.__client = CosS3Client(COS.__cos_config)

    @staticmethod
    def list_buckets():
        """
        查询存储桶列表
        :return:
        """
        return COS.__client.list_buckets()

    @staticmethod
    def file_easy_upload(file_path, bucket, key):
        """
        文件流简单上传 该操作会覆盖重名的文件
        :param file_path:文件路径
        :param bucket:桶名称
        :param key:文件名
        :return:Etag
        """
        with open(file_path, 'rb') as fp:
            response = COS.__client.put_object(
                Bucket=bucket,
                Body=fp,
                Key=key,
                StorageClass='STANDARD',
                EnableMD5=False
            )
        return response['ETag']

    @staticmethod
    def file_easy_upload_BytesIO(file, bucket, key):
        """
        文件流简单上传 该操作会覆盖重名的文件
        :param file:文件
        :param bucket:桶名称
        :param key:文件名
        :return:Etag
        """
        response = COS.__client.put_object(
            Bucket=bucket,
            Body=file,
            Key=key,
            StorageClass='STANDARD',
            EnableMD5=False
        )
        return response['ETag']

    @staticmethod
    def list_all_objects(bucket, prefix: str = ""):
        """
        查询所有对象
        :param bucket:桶名称
        :param prefix:文件夹
        :return:所有对象列表[{'Key','LastModified','Etag','Size','Owner':{'ID','DisplayName','StorageClass'}}]
        """
        res_list = []
        marker = ""
        while True:
            response = COS.__client.list_objects(
                Bucket=bucket,
                Prefix=prefix,
                Marker=marker
            )
            res_list = res_list + response['Contents']
            if response["IsTruncated"] == 'false':
                break
            marker = response["NextMarker"]
        return res_list

    @staticmethod
    def get_object_local(bucket, key, file_path):
        """
        下载文件到本地
        :param bucket:桶
        :param key: 文件名
        :param file_path:本地路径
        :return: None
        """
        response = COS.__client.get_object(
            Bucket=bucket,
            Key=key,
        )
        response['Body'].get_stream_to_file(file_path)

    @staticmethod
    def get_object_stream(bucket, key):
        """
        下载文件到文件流s
        :param bucket:桶
        :param key: 文件名
        :return: None
        """
        response = COS.__client.get_object(
            Bucket=bucket,
            Key=key,
        )
        return response['Body'].get_raw_stream()

    @staticmethod
    def get_poject_url(bucket, key):
        """
        获取对象url
        :param bucket:
        :param key:
        :return:
        """
        url = COS.__client.get_object_url(
            Bucket=bucket,
            Key=key
        )
        return url

    @staticmethod
    def get_presigned_download_url(Bucket, Key, Method='GET', Params=None, Headers=None, SignHost=False,
                                   Expired=60):
        """
        获取预签名下载链接
        :param Bucket:  桶名称
        :param Key:     文件名称
        :param Method:  HTTP方法
        :param Params:  参数
        :param Headers: 头
        :param SignHost:签名
        :param Expired: 过期时间
        :return:        预签名后的下载链接
        """
        url = COS.__client.get_presigned_url(
            Bucket=Bucket,
            Method=Method,
            Key=Key,
            Expired=Expired,  # Expired秒后过期，过期时间请根据自身场景定义
            Params=Params,
            Headers=Headers,
            SignHost=SignHost
        )
        return url

    @staticmethod
    def get_presigned_upload_url(Bucket, Key, Method='PUT', Params=None, Headers=None, SignHost=False,
                                 Expired=300):
        """
        获取预签名上传链接
        :param Bucket:  桶名称
        :param Key:     文件名称
        :param Method:  HTTP方法
        :param Params:  参数
        :param Headers: 头
        :param SignHost:签名
        :param Expired: 过期时间
        :return:        预签名后的上传链接
        """
        url = COS.__client.get_presigned_url(
            Method=Method,
            Bucket=Bucket,
            Key=Key,
            Params=Params,
            SignHost=SignHost,
            Headers=Headers,
            Expired=Expired  # 300秒后过期，过期时间请根据自身场景定义
        )
        return url

    @staticmethod
    def delete_object(bucket, key):
        """

        :param bucket:  桶名称
        :param key:     文件名称
        :return:        HTTP响应
        """
        response = COS.__client.delete_object(
            Bucket=bucket,
            Key=key
        )
        return response


cos_operator = COS()