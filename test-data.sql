insert into accounts (id, account, pwd, superuser) values (1, 'admin', 'a', 1);
insert into accounts (id, account, pwd, superuser) values (2, 'domain', 'a', 0);
insert into accounts (id, account, pwd, superuser) values (3, 'user', 'a', 0);

insert into domains (id, domain) values (1, 'test.dom');
insert into domains (id, domain) values (2, 'admin.dom');

insert into managed_domains (acc_id, dom_id) values (2, 1);
