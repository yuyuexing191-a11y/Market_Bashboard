# Alembic migrations

数据库结构只通过这里的版本迁移修改。导入命令不会调用
`Base.metadata.create_all()`，也不会在运行时执行建表 DDL。
