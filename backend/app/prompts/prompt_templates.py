INTENT_PARSER_PROMPT = """请解析以下用户查询，提取关键信息：

用户查询：{query}

相关表结构信息：
{schema_context}

请返回结构化的意图解析，包括：
1. 指标（需要计算的字段）
2. 维度（分组字段）
3. 筛选条件
4. 时间范围
5. 排序方式
6. 推荐图表类型

请以 JSON 格式返回。
"""

SQL_GENERATOR_PROMPT = """基于以下分析意图和表结构信息，生成 MaxCompute SQL：

分析意图：
{intent}

表结构信息：
{schema_info}

要求：
1. 生成符合 MaxCompute 语法的 SQL
2. 使用合适的表和字段
3. 包含必要的分区筛选
4. SQL 格式规范，有适当注释
"""
