# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2020-06-03 07:58
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        # Schema for Power DNS version 4.1.x as available on Github:
        # https://github.com/PowerDNS/pdns/blob/rel/auth-4.1.x/modules/gpgsqlbackend/schema.pgsql.sql
        migrations.RunSQL(sql="""
            BEGIN;
            /* PowerDNS 4.1.x Schema */
            CREATE TABLE IF NOT EXISTS domains (
              id                    SERIAL PRIMARY KEY,
              name                  VARCHAR(255) NOT NULL,
              master                VARCHAR(128) DEFAULT NULL,
              last_check            INT DEFAULT NULL,
              type                  VARCHAR(6) NOT NULL,
              notified_serial       BIGINT DEFAULT NULL,
              account               VARCHAR(40) DEFAULT NULL,
              CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
            );
            
            CREATE UNIQUE INDEX IF NOT EXISTS name_index ON domains(name);
            
            
            CREATE TABLE IF NOT EXISTS records (
              id                    BIGSERIAL PRIMARY KEY,
              domain_id             INT DEFAULT NULL,
              name                  VARCHAR(255) DEFAULT NULL,
              type                  VARCHAR(10) DEFAULT NULL,
              content               VARCHAR(65535) DEFAULT NULL,
              ttl                   INT DEFAULT NULL,
              prio                  INT DEFAULT NULL,
              change_date           INT DEFAULT NULL,
              disabled              BOOL DEFAULT 'f',
              ordername             VARCHAR(255),
              auth                  BOOL DEFAULT 't',
              CONSTRAINT domain_exists
              FOREIGN KEY(domain_id) REFERENCES domains(id)
              ON DELETE CASCADE,
              CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
            );
            
            CREATE INDEX IF NOT EXISTS rec_name_index ON records(name);
            CREATE INDEX IF NOT EXISTS nametype_index ON records(name,type);
            CREATE INDEX IF NOT EXISTS domain_id ON records(domain_id);
            CREATE INDEX IF NOT EXISTS recordorder ON records (domain_id, ordername text_pattern_ops);
            
            
            CREATE TABLE IF NOT EXISTS supermasters (
              ip                    INET NOT NULL,
              nameserver            VARCHAR(255) NOT NULL,
              account               VARCHAR(40) NOT NULL,
              PRIMARY KEY(ip, nameserver)
            );
            
            
            CREATE TABLE IF NOT EXISTS comments (
              id                    SERIAL PRIMARY KEY,
              domain_id             INT NOT NULL,
              name                  VARCHAR(255) NOT NULL,
              type                  VARCHAR(10) NOT NULL,
              modified_at           INT NOT NULL,
              account               VARCHAR(40) DEFAULT NULL,
              comment               VARCHAR(65535) NOT NULL,
              CONSTRAINT domain_exists
              FOREIGN KEY(domain_id) REFERENCES domains(id)
              ON DELETE CASCADE,
              CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
            );
            
            CREATE INDEX IF NOT EXISTS comments_domain_id_idx ON comments (domain_id);
            CREATE INDEX IF NOT EXISTS comments_name_type_idx ON comments (name, type);
            CREATE INDEX IF NOT EXISTS comments_order_idx ON comments (domain_id, modified_at);
            
            
            CREATE TABLE IF NOT EXISTS domainmetadata (
              id                    SERIAL PRIMARY KEY,
              domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
              kind                  VARCHAR(32),
              content               TEXT
            );
            
            CREATE INDEX IF NOT EXISTS domainidmetaindex ON domainmetadata(domain_id);
            
            
            CREATE TABLE IF NOT EXISTS cryptokeys (
              id                    SERIAL PRIMARY KEY,
              domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
              flags                 INT NOT NULL,
              active                BOOL,
              content               TEXT
            );
            
            CREATE INDEX IF NOT EXISTS domainidindex ON cryptokeys(domain_id);
            
            
            CREATE TABLE IF NOT EXISTS tsigkeys (
              id                    SERIAL PRIMARY KEY,
              name                  VARCHAR(255),
              algorithm             VARCHAR(50),
              secret                VARCHAR(255),
              CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
            );
            
            CREATE UNIQUE INDEX IF NOT EXISTS namealgoindex ON tsigkeys(name, algorithm);            
            COMMIT;""")
    ]
