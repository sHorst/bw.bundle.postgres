from base64 import b64decode, b64encode
from hashlib import pbkdf2_hmac, sha256
import hmac


def pg_scram_sha256(passwd: str, salt: bytes, iterations: int = 4096) -> str:
    digest_key = pbkdf2_hmac('sha256', passwd.encode('utf8'), salt, iterations, 32)
    client_key = hmac.digest(digest_key, b'Client Key', 'sha256')
    stored_key = sha256(client_key).digest()
    server_key = hmac.digest(digest_key, b'Server Key', 'sha256')
    return (
        f'SCRAM-SHA-256${iterations}:{b64encode(salt).decode('utf8')}'
        f'${b64encode(stored_key).decode('utf8')}:{b64encode(server_key).decode('utf8')}'
    )


POSTGRES_VERSION = 11

if node.os == 'debian' and node.os_version[0] == 11:
    POSTGRES_VERSION = 13
elif node.os == 'debian' and node.os_version[0] == 12:
    POSTGRES_VERSION = 15
elif node.os == 'debian' and node.os_version[0] == 13:
    POSTGRES_VERSION = 17

pkg_apt = {
    'postgresql': {},
    'postgresql-contrib': {}
}

svc_systemv = {
    'postgresql': {
        'needs': ['pkg_apt:postgresql']
    }
}

actions = {}
postgres_dbs = {}
postgres_roles = {}

for database_name, database_config in node.metadata.get('postgres', {}).get('databases', {}).items():
    postgres_roles[database_config['owner_name']] = {
        'superuser': database_config.get('owner_superuser', False),
        'needs': ['pkg_apt:postgresql']
    }
    if POSTGRES_VERSION >= 17:
        # use SCRAM-SHA256
        salt = repo.vault.random_bytes_as_base64_for(f'SALT_POSTGRESS_{node.name}_{database_name}_'
                                                     f'{database_config['owner_name']}', length=16)

        postgres_roles[database_config['owner_name']]['password_hash'] = pg_scram_sha256(
            str(database_config['owner_password']), b64decode(str(salt)))
    else:
        postgres_roles[database_config['owner_name']]['password'] = database_config['owner_password']

    postgres_dbs[database_name] = {
        'owner': database_config['owner_name'],
        'needs': ['pkg_apt:postgresql'],
        'when_creating': database_config.get('encoding', {
            "encoding": "UTF8",
            "collation": "de_DE.UTF8",
            "ctype": "de_DE.UTF8",
        }),
    }

for role_name, role_config in node.metadata.get('postgres', {}).get('roles', {}).items():
    postgres_roles[role_name] = {
        'superuser': role_config.get('superuser', False),
        'needs': ['pkg_apt:postgresql'],
    }
    if POSTGRES_VERSION >= 17:
        # use SCRAM-SHA256
        salt = repo.vault.random_bytes_as_base64_for(f'SALT_POSTGRESS_{node.name}_{role_name}', length=16)

        postgres_roles[role_name]['password_hash'] = pg_scram_sha256(
            str(role_config['password']), b64decode(str(salt)))
    else:
        postgres_roles[role_name]['password'] = role_config['password']

if node.metadata.get('postgres', {}).get('master', False):
    postgres_roles['replication'] = {
        'superuser': True,
        'needs': ['svc_systemv:postgresql']
    }
    if POSTGRES_VERSION >= 17:
        # use SCRAM-SHA256
        salt = repo.vault.random_bytes_as_base64_for(f'SALT_POSTGRESS_{node.name}_replication', length=16)

        postgres_roles['replication']['password_hash'] = pg_scram_sha256(
            str(repo.vault.password_for(f'postgres_replication_{node.name}')), b64decode(str(salt)))
    else:
        postgres_roles['replication']['password'] = repo.vault.password_for(f'postgres_replication_{node.name}')


bind_ips = ['127.0.0.1']
additional_interfaces = node.metadata.get('postgres', {}).get('additional_interfaces', [])
for interface in additional_interfaces:
    bind_ips.extend(node.metadata['interfaces'][interface]['ip_addresses'])

files = {
    f'/etc/postgresql/{POSTGRES_VERSION}/main/pg_hba.conf': {
        'content_type': 'mako',
        'mode': '0640',
        'owner': 'postgres',
        'group': 'postgres',
        'needs': ['pkg_apt:postgresql'],
        'triggers': ['svc_systemv:postgresql:restart']
    },
    f'/etc/postgresql/{POSTGRES_VERSION}/main/postgresql.conf': {
        'content_type': 'mako',
        'context': {
            'bind_ips': bind_ips,
            'version': POSTGRES_VERSION
        },
        'owner': 'postgres',
        'group': 'postgres',
        'needs': ['pkg_apt:postgresql'],
        'triggers': ['svc_systemv:postgresql:restart']
    },
}

if node.metadata.get('postgres', {}).get('cron_dump', True):
    files['/etc/cron.d/dump-postgres'] = {
        'content': '30 23 * * * root /usr/local/sbin/pg-dump-everything\n'
    }
    files['/usr/local/sbin/pg-dump-everything'] = {
        'source': 'pg-dump-everything.sh',
        'mode': '0750'
    }

    directories = {
        '/var/tmp/dumps/postgres': {
            'group': 'nagios' if node.has_bundle('nrpe') else 'root',
            'mode': '0750',
            'needs': ['pkg_apt:nagios-nrpe-server'] if node.has_bundle('nrpe') else []
        },
        '/var/tmp/dumps/postgres/dumps': {
            'group': 'nagios' if node.has_bundle('nrpe') else 'root',
            'mode': '0750',
            'needs': ['pkg_apt:nagios-nrpe-server'] if node.has_bundle('nrpe') else []
        },
        '/var/tmp/dumps/postgres/status': {
            'group': 'nagios' if node.has_bundle('nrpe') else 'root',
            'mode': '0750',
            'needs': ['pkg_apt:nagios-nrpe-server'] if node.has_bundle('nrpe') else []
        }
    }

