defaults = {}

if node.has_bundle('iptables'):
    defaults += (repo.libs.iptables.accept()
                 .chain('INPUT')
                 .input('main_interface')
                 .source('friendlies')
                 .state_new()
                 .tcp()
                 .dest_port('5432'))
