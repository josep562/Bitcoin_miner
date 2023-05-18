import hashlib
import requests
import json
import os
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class BitcoinMiner:

    def __init__(self, pool_url, pool_username, pool_password, payout_address):
        self.accounts = {}  # dictionary to store accounts
        self.target = ""  # target hash
        self.block_index = 0  # current block index
        self.transactions = {}  # dictionary to store transaction history
        self.logger = logging.getLogger('BitcoinMiner')
        self.logger.setLevel(logging.DEBUG)
        self.pool_url = pool_url
        self.pool_username = pool_username
        self.pool_password = pool_password
        self.payout_address = payout_address

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.logger.addHandler(ch)

        # create a session with retries and SSL verification
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 500, 502, 503, 504 ])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.verify = True

    def generate_account(self):
        # generate a new account with private key and address
        private_key = hashlib.sha256(os.urandom(16)).hexdigest()
        address = hashlib.sha256(str(private_key).encode('utf-8')).hexdigest()
        self.accounts[address] = private_key
        return address

    def get_info(self):
        # get current info from server
        response = self.session.get('https://blockchain.info/latestblock')
        data = json.loads(response.text)
        self.target = data['hash']
        self.block_index = data['height']

    def get_transaction_history(self, address):
        # get transaction history for a given address
        response = self.session.get('https://blockchain.info/address/' + address)
        data = json.loads(response.text)
        self.transactions[address] = data['txs']
        return self.transactions[address]

    def view_balance(self, address):
        # view balance of a given address
        response = self.session.get('https://blockchain.info/q/addressbalance/' + address)
        balance = float(response.text) / 100000000
        return balance

    def solve_nonce(self, address):
        # solve for valid nonce and broadcast to pool
        nonce = os.urandom(8)
        while True:
            # concatenate block data and nonce
            data = str(self.block_index) + self.target + self.accounts[address] + str(int.from_bytes(nonce, byteorder='big'))
            # hash the data
            hash_data = hashlib.sha256(data.encode('utf-8')).hexdigest()
            if hash_data < self.target:
                # valid nonce found, broadcast to pool
                response = self.session.post(self.pool_url, data={'nonce': str(int.from_bytes(nonce, byteorder='big')), 'user': self.pool_username, 'pass': self.pool_password, 'address': self.payout_address})
                if response.status_code == 200 and "true" in response.text:
                    self.logger.info(f"Nonce found and accepted by pool for account {address}")
                break
            else:
                nonce = os.urandom(8)

    def make_transaction(self, from_address, to_address, amount, nonce):
        # make a transaction from one address to another
        response = self.session.get('https://blockchain.info/unspent?active=' + from_address)
        data = json.loads(response.text)
        tx_input = []
        for tx in data['unspent_outputs']:
            tx_input.append({'txid': tx['tx_hash_big_endian'], 'vout': tx['tx_output_n'], 'script': tx['script']})
        tx_output = [{'value': amount, 'address': to_address}]
        transaction = {'inputs': tx_input, 'outputs': tx_output}
        # sign the transaction
        for i in range(len(transaction['inputs'])):
            tx = transaction['inputs'][i]
            txid = tx['txid']
            vout = tx['vout']
            script = tx['script']
            response = self.session.get('https://blockchain.info/rawtx/' + txid)
            data = json.loads(response.text)
            tx_hex = data['hex']
            tx_hex = tx_hex[:((vout * 2) + 2)] + '00' + tx_hex[((vout * 2) + 4):]
            sig = hashlib.sha256(str(self.accounts[from_address]).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            sig = hashlib.sha256(str(sig).encode('utf-8')).hexdigest()
            tx_hex = tx_hex[:110] + sig + tx_hex[142:]
            transaction['inputs'][i]['script'] = tx_hex
        # broadcast the transaction to the server
        response = self.session.post('https://blockchain.info/pushtx', data={'tx': str(transaction)})
        if response.status_code == 200:
            self.logger.info(f"Transaction made from {from_address} to {to_address} for {amount} BTC")
        return response

    def prevent_replay_attacks(self, address):
        # make sure the transaction is not replayed by checking the transaction history
        transaction_history = self.get_transaction_history(address)
        for transaction in transaction_history:
            if transaction['outputs'][0]['address'] == self.payout_address:
                # transaction has already been made, abort
                return False
        return True