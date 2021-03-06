# Deploying Q to Red Hat Enterprise Linux 7 / CentOS 7 / Amazon Linux 2

<!-- Please update the project's Vagrantfile when revising these instructions. -->

These instructions can be used to configure a Red Hat Enterprise Linux 7, CentOS 7, or Amazon Linux 2 system to run GovReady-Q.
A Vagrantfile based on CentOS 7 and these instructions is also provided at the root of the GovReady-Q source code.

## Preparing System Packages

GovReady-Q calls out to `git` to fetch apps from git repositories, but that requires git version 2 or later because of the use of the GIT_SSH_COMMAND environment variable. RHEL stock git is version 1. Switch it to version 2+ by using the IUS package:

    # if necessary, enable EPEL and IUS repositories
    rpm -i https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm https://rhel7.iuscommunity.org/ius-release.rpm

    # if necessary, remove any git currently installed
    yum remove git

    yum install git2u

## Preparing Q Source Code

Create a UNIX user named `govready-q`:

    # Create user.
    useradd govready-q -c "govready-q"
    
    # Change permissions so that Apache can read static files.
    chmod a+rx /home/govready-q

Deploy GovReady-Q source code:

    # Install required software.
    #
    # Note that python34-devel and mysql-devel are needed to compile & install
    # the mysqlclient Python package. But mysql-devl has an installation conflict
    # with IUS. Adding --disablerepo=ius fixes it.
    #
    # gcc is needed to build the uWSGI Python package.
    sudo yum install --disablerepo=ius \
        unzip gcc python34-pip python34-devel \
        graphviz \
        pandoc xorg-x11-server-Xvfb wkhtmltopdf \
        postgresql mysql-devel

Upgrade `pip` because the RHEL package version is out of date (we need >=9.1 to properly process hashes in `requirements.txt`):

    pip3 install --upgrade pip

Then switch to the govready-q user and install Q:

    sudo su govready-q
    cd
    git clone https://github.com/govready/govready-q
    cd govready-q
    git checkout {choose the tag for the current released version}
    pip3 install --user -r requirements.txt
    ./fetch-vendor-resources.sh
    
### Test Q with a Local Database

Run the final setup commands to initialize a local Sqlite3 database in `local/db.sqlite` to make sure everything is OK so far:

    python3 manage.py migrate
    python3 manage.py load_modules
    python3 manage.py createsuperuser

And test that the site starts in debug mode at localhost:8000:

	python3 manage.py runserver

### Set basic configuration variables

Create a file named `local/environment.json` (ensure it is not world-readable) that contains site configuration in JSON:

	{
	  "debug": false,
	  "host": "webserver.hostname.com",
	  "organization-parent-domain": "webserver.hostname.com",
	  "https": true,
	  "secret-key": "generate random string using e.g. https://www.miniwebtool.com/django-secret-key-generator/",
	  "static": "/home/govready-q/public_html/static"
	}

Because of host header checking, to test the site again using `python3 manage.py runserver` you will need to visit it using `webserver.hostname.com` and not `localhost`. (Be sure to replace `webserver.hostname.com` with your hostname.)

## Setting Up the Postgres Database Server

This deployment script uses PostgreSQL but other database servers may be used.

### On the database server

On the database server, install Postgres:
	
	yum install postgresql-server postgresql-contrib
	postgresql-setup initdb

In `/var/lib/pgsql/data/postgresql.conf`, enable TLS connections by changing the `ssl` option to

    ssl = on 

and enable remote connections by binding to all interfaces:

    listen_addresses = '*'

Enable remote connections to the database *only* from the web server and *only* encrypted with TLS by editing `/var/lib/pgsql/data/pg_hba.conf` and adding the line (replacing the hostname with the hostname of the Q web server):

    hostssl all all webserver.hostname.com md5
    
Generate a self-signed certificate (replace `db.govready-q.internal` with the database server's hostname if possible):

    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout /var/lib/pgsql/data/server.key -out /var/lib/pgsql/data/server.crt -subj '/CN=db.govready-q.internal'
    chmod 600 /var/lib/pgsql/data/server.{key,crt}
    chown postgres.postgres /var/lib/pgsql/data/server.{key,crt}

Copy the certificate to the web server so that the web server can make trusted connections to the database server:

    cat /var/lib/pgsql/data/server.crt
    # place on web server at /home/govready-q/pgsql.crt
    
Then restart the database:

    service postgresql restart

Then set up the user and database (both named `govready_q`):

    sudo -iu postgres createuser -P govready_q
    # paste a long random password
    
    sudo -iu postgres createdb govready_q

Postgres's default permissions automatically grant users access to a database of the same name.

And if necessary, open the Postgres port:

	firewall-cmd --zone=public --add-port=5432/tcp --permanent
	firewall-cmd --reload

### On the web server
    
On the web server, now check that secure connections can be made:

    psql "postgresql://govready_q@dbserver.hostname.com/govready_q?sslmode=verify-full&sslrootcert=/home/govready-q/pgsql.crt"

(It should fail if the TLS certificate file is not provided, if sslmode is set to `disable`, if a different user or database is given, or if the wrong password is given.)

Then in our GovReady-Q `local/environment.json` file, configure the database (replace `THEPASSWORDHERE`) by setting the following key:

        "db": "postgresql://govready_q:THEPASSWORDHERE@dbserver.hostname.com/govready_q?sslmode=verify-full&sslrootcert=/home/govready-q/pgsql.crt",

Then initialize the database content:

    python3 manage.py migrate
    python3 manage.py load_modules

And generate static files:

	python3 manage.py collectstatic

## Setting Up Apache & uWSGI

Install Apache 2.x with SSL (back to being root):

	yum install httpd mod_ssl

Copy the Apache config into place:

    cp /home/govready-q/govready-q/deployment/rhel/apache.conf /etc/httpd/conf.d/govready-q.conf

And then edit the file replacing `q.govready.com` and `*.govready.com` with your hostnames.

If you don't have a TLS certificate ready to use, create a self-signed certificate (replacing `webserver.hostname.com` with your hostname):

    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout /home/govready-q/ssl_certificate.key -out /home/govready-q/ssl_certificate.crt -subj '/CN=webserver.hostname.com'
    chmod 600 /home/govready-q/ssl_certificate.{key,crt}
    chown apache.apache /home/govready-q/ssl_certificate.{key,crt}

If SELinux is enabled (`sestatus` shows `SELinux status: enabled`), grant the Apache process access to these files as well as the site's static files:

	chcon -v -R --type=httpd_sys_content_t /home/govready-q/govready-q/deployment/rhel/apache.conf /home/govready-q/ssl_certificate.{key,crt} /home/govready-q/public_html

and grant Apache permission to make network connections so that it can connect to the Python/uwsgi backend running GovReady-Q:

	setsebool httpd_can_network_connect true

Install `supervisor` which will keep the Python/Django process running and symlink our supervisor config into place:

    yum install supervisor
    ln -s /home/govready-q/govready-q/deployment/rhel/supervisor.ini /etc/supervisord.d/govready-q.ini

Restart services:

    service supervisord restart
    service httpd restart

And if necessary open the web ports:

	firewall-cmd --zone=public --add-port=80/tcp --permanent
	firewall-cmd --zone=public --add-port=443/tcp --permanent
	firewall-cmd --reload

GovReady-Q should now be running and accessible at your domain name. Follow the instructions in the [main README.md](../../README.md) for creating your first organization.

## Creating the First User

If you are setting up a multi-tenant instance of Q where different organizations will use the site on different subdomains, create the administrative user using:

    python3 manage.py createsuperuser

and then log into the admin to create initial organizations.

Otherwise, for a single-tenant setup, add to `local/environment.json`:

  "single-organization": "main",

which will serve just the Organization instance whose subdomain field is "main", and then create the initial user and the "main" organization using:

	python3 manage.py first_run

You should now be able to log into GovReady-Q using the user created in this section.

## Setting up an HTTPS Certificate

The instructions above created a self-signed certificate to get the website up and running. To use Let's Encrypt to automatically provision a real certificate, install and run `certbot`:

	yum install -y python-certbot-apache
	certbot --apache -d webserver.hostname.com
	# and follow the prompts

Then set it to automatically renew certificates as needed:

	# edit root's crontab
	crontab -e

	# insert at end:
	30 2 * * * /usr/bin/certbot renew >> /var/log/le-renew.log

## Other Configuration Settings

Set up email by adding to `local/environment.json`:

	  "admins": [["Your Name", "you@company.com"]],
	  "email": {
	    "host": "smtp.server.com", "port": "587", "user": "...", "pw": "....",
	    "domain": "webserver.hostname.com"
	  },
	  "mailgun_api_key": "...",

## Updating Deployment

When there are changes to the GovReady-Q software, pull new sources and restart processes with:

    sudo -iu govready-q /home/govready-q/govready-q/deployment/rhel/update.sh
    
As root, you can also restart just the Python/Django process:    

    sudo supervisorctl restart all
    
But this won't do a full update so don't normally do that (it won't restart the separate notifications process or generate static assets, etc.).
