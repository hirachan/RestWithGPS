## How to Develop

### Local Development Environmet

#### Setup

Only do once on your server.
```
git config --global url."https://${GITHUB_TOKEN}@github.com/qualitia-cdev/".insteadOf "https://github.com/qualitia-cdev/"

pip install -U poetry
poetry config virtualenvs.in-project true
poetry install  # or poetry update
```

### Deploy to AWS Lambda

```
npm install
npx sls create-cert    # if with api gateway
npx sls create_domain  # if with api gateway
npx sls deploy
```

If you change packages, you might need to clear cache and remove generated requirements.txt.

```
sls requirements cleanCache
rm .serverless/requirements.txt
```

### Create Docker Image (by docker-compose)

```
cd YOUR_PARAMS_DIR/restwithgps/docker
docker-compose build
```

#### Invoke docker image

```
cd YOUR_PARAMS_DIR/restwithgps/docker
docker-compose up build
```

#### Access to API

You might need to wait for at most 40mins.

```
curl -XGET -H 'Origin: http://example.jp' -H 'Access-Control-Request-Method: GET' -H 'Access-Control-Request-Headers: Content-Type' --verbose https://restwithgps./hello/world
```
