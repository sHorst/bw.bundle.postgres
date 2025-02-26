global node

defaults = {}

if node.has_bundle('iptables'):
    defaults += (repo.libs.iptables.accept()
                 .chain('INPUT')
                 .input('main_interface')
                 .source('friendlies')
                 .state_new()
                 .tcp()
                 .dest_port('5432'))

@metadata_reactor
def add_restic_rules(metadata):
    if not node.has_bundle('restic'):
        raise DoNotRunAgain

    restic_user = metadata.get('restic/user', 'restic')
    restic_cmd = {}
    for db in metadata.get('postgres/databases', {}).keys():
        restic_cmd[f'postgres_{db}.sql.gz'] = (f'PGPASSWORD={repo.vault.password_for(f'user_{restic_user}_postgres_{node.name}')} '
                                               f'pg_dump -d {db} -c -C -U{restic_user} | '
                                               f'gzip --rsyncable')

    return {
        'postgres': {
            'roles': {
                restic_user: {
                    'password': repo.vault.password_for(f'user_{restic_user}_postgres_{node.name}'),
                    'superuser': True,
                },
            },
        },
        'restic': {
            'stdin_commands': restic_cmd,
        },
    }
