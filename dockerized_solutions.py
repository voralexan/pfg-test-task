import requests
import json
import docker
import pathlib
from docker.types import Mount

TARGET_HOST = 'https://hackattic.com'
ACCESS_TOKEN = ''
REGISTRY_URL = ''


if __name__ == '__main__':
    # Load initial cpnfiguration
    print ('Sending request to ' + TARGET_HOST + '/challenges/dockerized_solutions/problem?access_token=' + ACCESS_TOKEN + '\n')
    problem_json = json.loads(requests.get(TARGET_HOST + '/challenges/dockerized_solutions/problem?access_token=' + ACCESS_TOKEN).text)
    credentials_user = problem_json['credentials']['user']
    credentials_password = problem_json['credentials']['password']
    ignition_key = problem_json['ignition_key']
    trigger_token = problem_json['trigger_token']
    print('Initial JSON             = ', problem_json)
    print('Retrieved User ID        = ' + credentials_user)
    print('Retrieved Password       = ' + credentials_password)
    print('Retrieved Ignition Key   = ' + ignition_key)
    print('Retrieved Trigger Token  = ' + trigger_token + '\n')

    # Initialize docker client
    client = docker.from_env()

    # Create registry
    client.images.pull('registry:2')
    with open(str(pathlib.Path().resolve()) + "/auth/htpasswd", "w") as file:
       file.write(client.containers.run(image="httpd:2", entrypoint="htpasswd", command="-Bbn " + credentials_user + " " + credentials_password).decode("utf-8"))

    m1 = Mount(source=str(pathlib.Path().resolve()) +
               "/auth", target="/auth", type="bind")
    m2 = Mount(source=str(pathlib.Path().resolve()) +
               "/certs", target="/certs", type="bind")

    container = client.containers.run(image="registry:2", detach=True, mounts=[m1, m2],
                                      environment={"REGISTRY_AUTH": "htpasswd", "REGISTRY_AUTH_HTPASSWD_PATH": "/auth/htpasswd",
                                                   "REGISTRY_HTTP_TLS_CERTIFICATE": "/certs/domain.crt", "REGISTRY_HTTP_TLS_KEY": "/certs/domain.key",
                                                   "REGISTRY_HTTP_ADDR": "0.0.0.0:443", "REGISTRY_AUTH_HTPASSWD_REALM": "Registry Realm"},
                                      ports={443: 443}, restart_policy={"Name": "always"}, name="registry")


    # Triggger container push
    print("Trigger push on " + TARGET_HOST + '/_/push/' + trigger_token + 'with data = {' + "registry_host:" + REGISTRY_URL + '}' + '\n')
    result = requests.post(url=TARGET_HOST + '/_/push/' + trigger_token,
                           json={"registry_host": REGISTRY_URL})

    # Parse tags from the output
    push_json = json.loads(result.text)
    tags = [json.loads(line)['aux']['Tag']
            for line in push_json['logs'].split('\n') if "Tag" in line]
    print('Retrieved images with the follwong tags = ',tags)

    # Pull the newly pushed images and try getting the answer
    client.login(username=credentials_user,
                 password=credentials_password, registry=REGISTRY_URL)
    secret = None
    for tag in tags:
        client.images.pull(REGISTRY_URL+'/hack:'+tag)
        result = client.containers.run(image=REGISTRY_URL+'/hack:'+tag,
                                    environment={"IGNITION_KEY": ignition_key}).decode("utf-8")
        print("Running a container returned :" + result)
        if "wrong" not in result:
            secret = str.strip(result)

    # Submit a solution
    print('Received a secret: ' + secret + '\n')
    print('Sending request with a solution to ' + TARGET_HOST + '/challenges/dockerized_solutions/solve?access_token=' + ACCESS_TOKEN +
    'with data {' + "secret:" + secret + '\n')
    print(requests.post(url=TARGET_HOST + '/challenges/dockerized_solutions/solve?access_token=' + ACCESS_TOKEN,
                         json={"secret": secret}).text)

    # Cleanup
    container.stop()
    container.remove()
