from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import boto3
import botocore.session
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from app.storage import LocalStore, S3Store, StorageConflict


def test_local_original_bytes_paths_and_concurrent_no_overwrite(tmp_path):
    store = LocalStore(tmp_path)
    key = 'files/Fictional Drawings/Employee chosen filename.PDF'
    def write(content):
        try:
            store.put_new(key, content)
            return True
        except StorageConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, [b'original A', b'original B']))
    assert sorted(results) == [False, True]
    assert store.read(key) in (b'original A', b'original B')
    with pytest.raises(ValueError):
        store.put_new('../escape', b'no')
    (tmp_path / 'link').symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        store.read('link/escape')


def test_s3_conditional_encrypted_write_and_exact_download(monkeypatch):
    monkeypatch.delenv('AWS_PROFILE', raising=False)
    monkeypatch.delenv('AWS_DEFAULT_PROFILE', raising=False)
    session = botocore.session.Session()
    session.set_config_variable('profile', None)  # Stubbed test must not select a real identity.
    session.set_credentials('fictional', 'fictional')
    client = session.create_client('s3', region_name='us-east-1')
    store = S3Store('fictional-bucket', 'qwoms', client)
    key = 'files/Folder/Employee filename.xlsx'
    expected = {'Bucket': 'fictional-bucket', 'Key': 'qwoms/' + key, 'Body': b'original',
                'IfNoneMatch': '*', 'ServerSideEncryption': 'AES256'}
    with Stubber(client) as stub:
        stub.add_response('put_object', {}, expected)
        store.put_new(key, b'original')
        stub.add_client_error('put_object', service_error_code='PreconditionFailed',
                              http_status_code=412, expected_params=expected)
        with pytest.raises(StorageConflict):
            store.put_new(key, b'original')
        stub.add_response('get_object', {'Body': StreamingBody(BytesIO(b'original'), 8)},
                          {'Bucket': 'fictional-bucket', 'Key': 'qwoms/' + key})
        assert store.read(key) == b'original'
        stub.add_client_error('get_object', service_error_code='NoSuchKey', http_status_code=404,
                              expected_params={'Bucket': 'fictional-bucket', 'Key': 'qwoms/' + key})
        with pytest.raises(FileNotFoundError):
            store.read(key)
