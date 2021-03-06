# Deploying GovReady-Q with Docker

#### GovReady-Q on Docker Hub

| Container                 | Where                                                                                                           |
|---------------------------|-----------------------------------------------------------------------------------------------------------------|
| Current Release on Docker | [https://hub.docker.com/r/govready/govready-q/](https://hub.docker.com/r/govready/govready-q/)                  |
| Nightly Build on Docker   | [https://hub.docker.com/r/govready/govready-q-nightly/](https://hub.docker.com/r/govready/govready-q-nightly/)  |


## Running the Docker container

Make sure you first [install Docker](https://docs.docker.com/engine/installation/) and, if appropriate, [grant non-root users access to run Docker containers](https://docs.docker.com/engine/installation/linux/linux-postinstall/#manage-docker-as-a-non-root-user) (or else use `sudo` when invoking Docker below).

Start the container in the background:

	docker container run --name govready-q --detach -p 8000:8000 govready/govready-q

For more complex setups, using our run script instead will be easier:

	wget https://raw.githubusercontent.com/GovReady/govready-q/master/deployment/docker/docker_container_run.sh
	chmod +x docker_container_run.sh
	./docker_container_run.sh

Visit your GovReady-Q site in your web browser at:

	http://localhost:8000/

It may not load at first as it initializes your database for the first time. Wait for the site to become available.
Because of HTTP Host header checking, you must use `localhost` to access the site or another hostname if configured
using the `--address` option documented below.

If the site does not come up, check the container logs for an error message:
	
	docker container logs govready-q

With the container started and the database initialized, run our first-run script to create a Django database superuser and set up your first organization:

	docker container exec -it govready-q first_run

To pause and restart the container without destroying its data:

	docker container stop govready-q
	docker container start govready-q

To destroy the container and all user data entered into Q:

	docker container rm -f govready-q

Notes:

* The Q database is only persisted within the container by default. The database will persist between `docker container stop`/`docker container start` commands, but when the container is removed from Docker (i.e. using `docker container rm`) the Q data will be destroyed. See the _Persistent database_ section below for connecting to a database outside of the container.
* The Q instance cannot send email or receive comment replies until it is configured to use a transactional mail provider like Mailgun -- see below.
* This image is not meant to be used for a public website because it uses Django's debug server to serve the site with `DEBUG = True`.

## Advanced configuration of GovReady-Q inside Docker

Advanced container options can be set with command-line arguments to our container run script:

	./docker_container_run.sh ...additional arguments here...

### Changing the hostname and port

#### The public address (as users see it)

The container will run at `localhost:8000` by default, it will only be accessible from the
host machine, and because of HTTP Host header checking you must visit GovReady-Q using the
same hostname it is configured to run at (so, with default settings, visiting `127.0.0.1`
instead of `localhost` will result in an error).

You may change the hostname and port of the GovReady-Q server using:

	--address q.mydomain.com:80

If the Docker container is behind a proxy, then `--address` specifies the public address
that end-users will use to access GovReady-Q. This may differ from the address and port that the container is accessed at on your organization's network, which is set using `--bind`.

Add `--https` if end users will access GovReady-Q with https: URLs. This must be done through a proxy that accepts HTTPS connections and passes the requests using HTTP to the Docker container. See the `HTTPS` environment variable, below.

#### The address that the container is bound to

Use `--bind IP:PORT` to control how the listening socket is created on the host machine.
The default value of `--bind` is `127.0.0.1` and the port from `--address`, or `127.0.0.1:8000` if
`--address` isn't given. If the host machine is behind a proxy, use `--bind` to control the
network interface and port that Docker will forward to the GovReady-Q container.

	--bind 10.0.0.5:6543

### Persistent database

In a production environment it is important to have GovReady-Q connect to a
persistent database instead of the database stored inside the container,
which will be destroyed when the container is destroyed. There are two methods
for connecting to a persistent database.

#### Sqlite file

You can use a Sqlite file stored on the host machine:

	--sqlitedb /path/to/govready-q-database.sqlite

You must specify an absolute path. The path is mounted using a Docker bind mount into the container filesytem.

The file must be readable & writable by the container process, which is running as user 1000/group 1000. Although the container is running as a user isolated from the host environment, filesystem permissions for mounted files are based on comparing the raw user/group IDs of the file's owner/group on the host to the raw user/group ID of the process running in the container. Consider granting user 1000 read/write permission to the database using ACLs:

	setfacl -m u:1000:rw /path/to/govready-q-database.sqlite

Of course, do not do this if the host machine has a user 1000 that you do not trust.

#### Remote database

You can also connect to a database running on a remote system accessible to
the Docker container.

For instance, you might run a second Docker container holding a Postgres
server.

	DBPASSWORD=mysecretpassword
	docker container run --name govready-q-db -e POSTGRES_PASSWORD=$DBPASSWORD -d postgres
	DBHOST=$(docker container inspect govready-q-db | jq -r .[0].NetworkSettings.IPAddress)
	DBUSER=postgres
	DBDATABASE=postgres

(This example uses `jq`, a JSON parsing tool, to extract the IP address of the database container. You can install `jq` or just set `DBHOST` manually by looking for the IP address in `docker container inspect govready-q-db`.)

Start the GovReady-Q container with the argument:

	--dburl postgres://$DBUSER:$DBPASSWORD@$DBHOST/$DBDATABASE

where `$DBHOST` is the hostname of the database server, `$DBDATABASE` is the name of the database, and `$DBUSER` and `$DBPASSWORD` are the credentials for the database.

You can also use a MySQL or MariaDB server using the syntax `mysql://USER:PASSWORD@HOST:PORT/NAME`.

### Configuring email

GovReady-Q sends outbound emails for notifications about invitations and discussions.
It also receives inbound emails --- replies to dicussion notifications can be used to
post discussion comments by email.

To configure outbound email, add:

	--email-host smtp.company.org --email-port 587 --email-user ... --email-pw ... --email-domain q.company.org

`--email-domain` sets the hostname used in the email address of outbound email. The other arguments set the SMTP relay server details.

Some of GovReady-Q's outbound emails can be replied to. When a user replies to a notification of a discussion comment, the reply's body is post as a new comment on the discussion. Currently we only support an incoming notification hook from Mailgun, and it is not yet configurable for the docker deployment. TODO

### Container management and other options

Use `--name NAME` to specify an alternate name for the container. The default is `govready-q`.

Use `--relaunch` to remove an existing container of the same name before launching
the new one, if an existing container of the same name exists. This simply runs
`docker container rm -f NAME`.

Add `--debug` to start GovReady-Q in DEBUG mode, which enables nicer error messages. Do not use in production.

### Developing compliance apps

If you are using the Docker image to develop your own compliance apps, then
you will need to bind-mount a directory on your (host) system as a directory
within the container so that the container can see your app YAML files. To
do so, start the container with the additional command-line argument:

	--appsdevdir /path/to/apps

The directory may be empty but it must exist, and you must specify it as an
absolute path (due to a Docker limitation).

The directory and its contents must also be readable --- and writable, if you
intend to use GovReady-Q's authoring tools --- by the container process. The
container process is running as user 1000/group 1000. Although the container
is running as a user isolated from the host environment, filesystem permissions
for mounted files are based on comparing the raw user/group IDs of the file's
owner/group on the host to the raw user/group ID of the process running in the
container.  Consider granting user 1000 read/write permission to the files,
plus execute (i.e. browse) permission to the directories, in the mounted path
using ACLs:

	setfacl -R -m u:1000:rwX /path/to/apps

Of course, do not do this if the host machine has a user 1000 that you do not trust.

If the directory is not empty, it should have subdirectories for each of your apps.
For instance, you would have a YAML file at `/path/to/apps/my_app/app.yaml`.

To create your first app, you can run

	docker container exec -it govready-q python3.6 manage.py compliance_app host your_new_app_name

Replace `your_new_app_name` with an app identifier, which may contain letters,
numbers, dashes, and underscores. `host` is always just `host` --- don't change
that.

If your new app does not appear in the compliance apps catalog, you may need
to force the app catalog cache to be cleared by restarting the container:

	docker container restart govready-q

## Production deployment of the Docker container

The GovReady-Q container runs several processes, including an HTTP/application server and a background process for sending notification emails.

### Console and logs

The container's console, which can be accessed with

	docker container logs govready-q

shows the output of container's start-up commands including database migrations and process startup.

Additional log files are stored in /var/log within the container. These files contain access logs and other program output, including logs for unhandled error messages that appear as 500 Internal Server Error pages to end users. A special management command can be used to see the log files:

	docker container exec govready-q tail_logs

`tail_logs` takes the same arguments as Unix `tail`. For instance, add `-n 1000` to see the most recent 1,000 log lines, or add `-f` to continue to output the logs as the log files grow.

The log files can also be accessed by mounting `/var/log` with a Docker bind-mount or as a volume (and that's the only way to see the logs if `docker container exec` cannot be used in your environment).

### Secure deployments

The container's processes run exclusively as a non-root user with UID 1000 and GID 1000.

The container may be run with a read-only root filesystem (Docker's `--read-only` argument) so long as `/run`, `/tmp`, and `/var/log` are writable. When the `--dburl` argument is given to our `docker_container_run.sh` script, a read-only filesystem is activated using:

	--read-only --tmpfs /run --tmpfs /tmp --tmpfs /var/log

The three directories can be made writable either by being mounted as tmpfs temporary filesystems, as above, or using a bind mount or a Docker volume. In production environments where the container is launched without our script, it is recommended to use tempfs for `/run` and `/tmp` and to mount `/var/log` to a volume.


### Other management commands

See the [uWSGI](http://uwsgi-docs.readthedocs.io/) application server JSON process stats:

	docker container exec govready-q uwsgi_stats

## Updating to a new release of GovReady-Q

Periodically there will be a new release of GovReady-Q as an new image on the Docker Hub. Updating is easy by re-running the same commands again.

1) There may be an update to `docker_container_run.sh`. Since this script is not a part of the Docker image, you will need to get it again from this Github repository.

2) You should be using a persistent database as described above. When using a persistent database, it is safe to detroy the `govready-q` Docker container and start a new one to deploy an update.

3) Use the same arguments to `docker_container_run.sh` as when you started the container the last time, but add `--relaunch` to kill the previous container --- you cannot have two containers with the same name or two containers listening on the same port. (You can change the name and port, as described above, if you would like to keep the old container running.)

4) When the new container starts, database migrations will be applied, if applicable.

For example:

	# Update docker_container_run.sh, replacing the old script (with -O).
	wget -O docker_container_run.sh \
	    https://raw.githubusercontent.com/GovReady/govready-q/master/deployment/docker/docker_container_run.sh
	chmod +x docker_container_run.sh
	
	# Remove old container and launch updated container.
	./docker_container_run.sh --relaunch [your same command-line arguments]


## Environment variables for launching the container without our run script

The following environment variables are used to configure the container when launching GovReady-Q using `docker run` or a container service (i.e., not when using our `docker_container_run.sh` helper script).

`HOST` - The domain name that GovReady-Q will be accessible at by end users. (Default: `localhost`)

`PORT` - The port that GovReady-Q will be accessed at by end users, typically either 80 (no HTTPS) or 443 (HTTPS). (Default: `8080`)

`HTTPS` - Set to `true` if GovReady-Q will be accessed by end users at an https: address.  This must be done through a proxy that accepts HTTPS connections and passes the requests using HTTP to the Docker container. The proxy must set the `X-Forwarded-Proto: https` header. It is also permissible for the proxy to forward HTTP requests, and those requests will be automatically redirected to the https: URL. (Default: `false`)

`DEBUG` - Set to `true` to run in Django debug mode. (Default: `false`)

`DBURL` - Set to a database connection string as described in [https://github.com/kennethreitz/dj-database-url](https://github.com/kennethreitz/dj-database-url). We recommend using PostgreSQL [using a TLS server certificate](https://www.postgresql.org/docs/9.1/static/libpq-ssl.html), e.g. `postgresql://user:password@dbhost/govready_q?sslmode=verify-full&sslrootcert=/path/to/pgsql.crt` (although you'll have to figure out how to get the server certificate accessible via the container filesystem). (Default: Not set, which means using a Sqlite database stored in the container at `/usr/src/app/local/database.sqlite`, which will be ephemeral if the path is not mounted to the host or a Docker volume.)

`ORGANIZATION_PARENT_DOMAIN` - If not set, GovReady-Q will be single-tenant and the database must be configured with a single organization whose subdomain is `main`. If set, GovReady-Q will be multi-tenant, serving a landing page and organization-specific sites on different domain names. A landing/signup page and the Django `/admin` site will be available at the domain name given in the `HOST` environment variable and organization sites will be served at subdomains of the `ORGANIZATION_PARENT_DOMAIN` domain name value. (Default: Not set).

`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PW`, and `EMAIL_DOMAIN` - For enabling outbound email. The host, port, username, and password settings specify a TLS-enabled SMTP server. `EMAIL_DOMAIN` is the domain name to use in outbound mail. (Default: Not set and outbound emails are dumped to logs for debugging.) To test the email configuration from the command-line, you can run `docker container exec -it govready-q python3.6 manage.py sendtestemail you@example.com`. If email is configured, you should not see any output and you should get a test email.

`FIRST_RUN` - If set to `1`, an administrator user will be created when the container launches and a randomly generated password will be given to the user and printed on the console, which will be visible in the container's logs. An organization with subdomain `main` will also be created.

`PROCESSES` - The number of concurrent requests that can be handled by the container. (Default: 4)

`SECRET_KEY` - The [Django SECRET_KEY](https://docs.djangoproject.com/en/2.0/ref/settings/#secret-key) for session management. (Try [this tool](https://www.miniwebtool.com/django-secret-key-generator/) to generate one.)

`ADMINS` - The [Django ADMINS](https://docs.djangoproject.com/en/2.0/ref/settings/#admins) setting, passed as raw JSON. Example: `[["Admin Name 1", "admin1@example.com"], ["Admin Name 2", "admin2@example.com"]]`. (Default: Empty list, i.e. `[]`.)

`SYSLOG` - The host and port of a syslog-compatible log message sink. (Default: None.)

`MAILGUN_API_KEY` - An API key for Mailgun which is used to validate incoming webhook requests from Mailgun when an incoming email is received, when Mailgun is configured to handle incoming mail. (Default: None)

`BRANDING` (downstream packaging only): You may override the templates and stylesheets that are used for GovReady-Q's branding by setting this environment variable to the name of an installed Django app Python module (i.e. created using `manage.py startapp`) that holds templates and static files. No such app is provided in the GovReady-Q published Docker image, so this variable can only be used by downstream image maintainers.

## Building and publishing the Docker image for GovReady-Q maintainers

You may build the Docker image locally from the current source code rather than obtaining it from the Docker Hub. Prior to building the image:

* Ensure that you have no uncommitted source code changes.
* Tag your HEAD commit in the format `v1.2.3-rc0`.
* If you are a GovReady-Q maintainer, push the tag to Github.

In the root directory of this repository, build the Docker image:

	deployment/docker/docker_image_build.sh

If you are a GovReady-Q maintainer, you can then push the image to hub.docker.com:

	docker login
	# respond to prompts with credentials
	docker image push govready/govready-q

Or to an AWS Elastic Container Registry:

	aws ecr get-login --region us-east-1
	docker login -u AWS -p ... # copy from output of last line, but remove '-e none'
	REGISTRYURI=...dkr.ecr...amazonaws.com/name
	docker tag govready/govready-q:latest $REGISTRYURI:latest
	docker push $REGISTRYURI:latest

## Running tests

GovReady-Q's unit tests can be run within the Docker container. After building the image:

	docker container run --rm -it govready/govready-q:latest python3.6 manage.py test

Or once a Docker container running GovReady-Q is started (and named `govready-q`), use `exec` to begin a shell within the container, and then launch the unit tests:

	docker container exec -it govready-q bash
	python3.6 manage.py test guidedmodules

The functional tests run a headless Chromium web browser session and we have not yet figured out how to get this to work in our Docker container. Chromium's process isolation capabilities seem to require special system privileges (i.e. `docker run --privileged --cap-add SYS_ADMIN`) or Chromium command-line flags (`--no-sandbox --disable-gpu`).

	yum install -y chromium chromedriver
	python3.6 manage.py test
	...
	selenium.common.exceptions.WebDriverException: Message: unknown error: Chrome failed to start: exited abnormally

## Deployment the Docker container on Amazon Web Services Elastic Container Service with AWS Fargate

### Preparation

* In the AWS VPC console, use the Start VPC Wizard to create a new "VPC with a Single Public Subnet". After creating it, go to the Subnets tab and find the subnet and rename it to, e.g., GovReady-Q Production Public Subnet 1. Check which Availability Zone it uses. Then add a second Subnet in the same VPC. Use similar settings as the first subnet but a) choose a different Availability Zone because an Elastic Load Balancer requires operating two zones and b) modify the IPv4 CIDR block because it must be different (if the first subnet used 10.0.0.0/24, you can use 10.0.1.0/24 here). Then edit the new Subnet's Route Table to use the same Route Table as the first Subnet, and delete the new subnet's previous-and-now-unused route table.
* In the AWS EC2 console, create a Security Group in the new VPC for the Load Balancer and any other public-facing systems. Enable inbound HTTP and HTTPS traffic.
* Create a new Load Balancer using the Application Load Balancer type. Select internet-facing. Add a listener on HTTPS (port 80) and/or HTTPS (port 443). Use the VPC just created and the Security Group for public facting systems. Create a dummy target group if you have to --- we won't use this --- and skip registering targets.
* Edit the VPC's default Security Group, which we'll use for all non-public-facing systems, to permit all inbound traffic from the new public facing security group.
* In AWS RDS, create a Postgres database instance. For simplicity, use `govready_q` as the root username and database name. Choose the VPC created above, one of the Availability Zones tied to VPC's two subnets, and the default VPC security group.

### In AWS ECS

* Create a new Task Definition using the Fargate launch type. Leave the task role blank. The task size is up to you.
* Add a container with image `govready/govready-q` to use a GovReady image on the Docker Hub. (If using an AWS Elastic Container Registry, specify an image like `...dkr.ecr...amazonaws.com/repository-name:latest`. After creating the ECS Task Definition, go back to ECR and add the "Pull only actions" permission for the Task Definition's role, which is probably `ecsTaskExecutionRole`.)
* Add a port mapping for port 8000 (there source and destination ports here at the same).
* Set the environment variables as appropriate for your deployment (see above). Set the `HOST` environment variable to match the public DNS name of the load balancer. Set `DBURL` to use the RDS database using e.g. `postgresql://govready_q:password@...rds.amazonaws.com/govready_q?sslmode=require`.
* Leave `Auto-configure CloudWatch Logs` on so that the container's console output is available in CloudWatch.
* Save the Task Definition.
* Create a Cluster using the "Networking only (powered by AWS Fargate)" template. Don't create a VPC (you already did that).
* Create a Service in the new Cluster. Set launch type to Fargate. Choose the Task Defintion.
* Choose the same VPC that was created above, the subnet the RDS database is in, and the VPC's default security group. Auto-assign public IP must be Enabled so that it can have routing to the Internet. Choose the Application Load Balancer created early. Click to add the Task Definition's container to the load balancer for each of HTTP and HTTPS as appropriate (all ports the load balancer is listening on --- if using HTTPS, GovReady-Q will issue redirects from HTTP to HTTPS), and set the Path Pattern to `/*` and Evaluation Order to 1 for each.
* Enable service discovery.
* Go to the EC2 console and in Target Groups find the Target Group that was created by ECS. Edit its Health Checks. Set the health check to the path `/health-check` and add status codes `400,404` to the acceptable status codes because at this time Load Balancer status checks will not send a valid HTTP Host: header and Django will reject the request with a 400 response code, and if that were fixed the `/health-check` page isn't yet implemented.

### Post deployment steps

* If using HTTPS, import a certificate into AWS Certificate Manager and apply it to the Load Balancer.