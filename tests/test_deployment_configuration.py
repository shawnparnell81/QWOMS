from pathlib import Path
import yaml


def test_render_blueprint_is_free_private_and_synthetic():
    spec=yaml.safe_load(Path('render.yaml').read_text())
    assert spec['services'][0]['plan']=='free'
    assert spec['databases'][0]['plan']=='free'
    assert spec['databases'][0]['ipAllowList']==[]
    service=spec['services'][0]
    assert service['branch']=='development/qwoms-complete-build'
    assert service['healthCheckPath']=='/readyz'
    assert 'disk' not in service and 'preDeployCommand' not in service
    env={item['key']:item for item in service['envVars']}
    assert env['QWOMS_DEMO_ACCESS_MODE']['value']=='network'
    assert env['QWOMS_STORAGE_BACKEND']['value']=='database'
    for key in ['QWOMS_DEMO_MODE','QWOMS_COOKIE_SECURE','QWOMS_DATABASE_REQUIRE_TLS','QWOMS_SYNTHETIC_DATA_ONLY']:
        assert env[key]['value']=='true'
    for key in ['QWOMS_SECRET_KEY','QWOMS_DEMO_GATE_PASSWORD','QWOMS_BOOTSTRAP_PASSWORD']:
        assert env[key]['generateValue'] is True and 'value' not in env[key]
