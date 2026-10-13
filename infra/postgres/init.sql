CREATE USER workforce_user WITH PASSWORD 'workforce_pass';
CREATE DATABASE workforce_db OWNER workforce_user;

CREATE USER dispatch_user WITH PASSWORD 'dispatch_pass';
CREATE DATABASE dispatch_db OWNER dispatch_user;
