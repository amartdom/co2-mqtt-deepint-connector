#!usr/bin/python

# Copyright 2021 AIR Institute
# See LICENSE for details.


import json
import base64
import deepint
import pandas as pd
from Crypto.Cipher import AES
from typing import Dict, List, Any

from co2_mqtt_deepint_connector import serve_application_logger


logger = serve_application_logger()


def debug_errored_messages(cause, message, organization, workspace, source):
    import datetime
    import pandas as pd

    try:
        df = pd.read_csv('errored_messages.csv')
    except:
        df = pd.DataFrame(data={
            'date': []
            , 'cause': []
            , 'organization': []
            , 'workspace': []
            , 'source': []
            , 'message': []
        })

    new_df = pd.DataFrame(data=[{
        'date': datetime.datetime.now(),
        'cause': cause,
        'organization': organization,
        'workspace': workspace,
        'source': source,
        'message': message
    }])

    df = pd.concat([df, new_df], ignore_index=True)

    df.to_csv('errored_messages.csv', index=False)


class DeepintProducer:
    """Produces to AIR Institute the given data, updating a source.

    Attributes:
        conn: connection to a deepint.net source.

    Args:
        auth_token: Authentication token for AIR Institute.
        organization_id: Deep intelligence organization's id, where source is located.
        workspace_id: Deep intelligence workspace's id, where source is located.
        source_id: Deep intelligence source's id, where data will be dumped.
    """

    def __init__(self, auth_token: str, organization_id: str, workspace_id: str, source_id: str, cipher_key: str = None, key_size: int = 16) -> None:
        self.source_id = source_id
        self.workspace_id = workspace_id
        self.organization_id = organization_id
        self.credentials = deepint.Credentials.build(token=auth_token)
        self.cipher_key = cipher_key[:key_size]

    def decript_string(self, data):

        if self.cipher_key is not None:

            # decode data
            data = base64.b64decode(data)     

            # decrypt data 
            decipher = AES.new(self.cipher_key, AES.MODE_ECB)
            data = decipher.decrypt(data)
            data = data.decode('ascii').strip().replace('\t', '')

            # select only json data 
            start_position = data.index('{')
            end_position = data.index('}')
            data = data[start_position:end_position+1].strip()

        data = json.loads(data)

        return data

    def produce(self, data: List[str]) -> None:
        """Produces the given data to AIR Institute
        
        Args:
            data: JSON formatted data to dump into AIR Institute.
        """
        try:
            data = [self.decript_string(d) for d in data]
        except Exception as e:
            debug_errored_messages('CIPHER', data, self.organization_id, self.workspace_id, self.source_id)
            logger.warning(f'Exception during message decrypt process: {e}')

        try:
            # build dataframe with data
            df = pd.DataFrame(data=data)

            # build source
            source = deepint.Source.build(
                    credentials=self.credentials
                    ,organization_id=self.organization_id
                    ,workspace_id=self.workspace_id
                    ,source_id=self.source_id
                )

            # create dataframe and send it to deep intelligence
            logger.info(f"publishing {len(df)} messages to source {self.source_id}")
            t = source.instances.update(data=df, replace=False)
            #t.resolve()
    
            logger.info('finished message producing succesfully')
        except Exception as e:
            debug_errored_messages('PRODUCE', data, self.organization_id, self.workspace_id, self.source_id)
            logger.warning(f'Exception during Deep Intelligence source update {e}')
