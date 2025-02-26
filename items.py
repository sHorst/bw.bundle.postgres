POSTGRES_VERSION = '11'

if node.os == 'debian' and node.os_version[0] == 11:
    POSTGRES_VERSION = '13'

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
        'password': database_config['owner_password'],
        'superuser': database_config.get('owner_superuser', False),
        'needs': ['pkg_apt:postgresql']
    }
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
        'password': role_config['password'],
        'superuser': role_config.get('superuser', False),
        'needs': ['pkg_apt:postgresql'],
    }

if node.metadata.get('postgres', {}).get('master', False):
    postgres_roles['replication'] = {
        'superuser': True,
        'password': repo.vault.password_for('postgres_replication_{}'.format(node.name)),
        'needs': ['svc_systemv:postgresql']
    }


bind_ips = ['127.0.0.1']
additional_interfaces = node.metadata.get('postgres', {}).get('additional_interfaces', [])
for interface in additional_interfaces:
    bind_ips.extend(node.metadata['interfaces'][interface]['ip_addresses'])

files = {
    '/etc/postgresql/{}/main/pg_hba.conf'.format(POSTGRES_VERSION): {
        'content_type': 'mako',
        'mode': '0640',
        'owner': 'postgres',
        'group': 'postgres',
        'needs': ['pkg_apt:postgresql'],
        'triggers': ['svc_systemv:postgresql:restart']
    },
    '/etc/postgresql/{}/main/postgresql.conf'.format(POSTGRES_VERSION): {
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
    '/etc/cron.d/dump-postgres': {
        'content': '30 23 * * * root /usr/local/sbin/pg-dump-everything\n'
    },
    '/usr/local/sbin/pg-dump-everything': {
        'source': 'pg-dump-everything.sh',
        'mode': '0750'
    }
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

