# coding=utf-8
import json
from pyflink.dataset import ExecutionEnvironment
from pyflink.table import TableConfig, BatchTableEnvironment, SqlDialect, EnvironmentSettings, TableEnvironment, \
    DataTypes
import argparse
from pyflink.table.catalog import HiveCatalog
from pyflink.table.udf import udf, udtf
from chloe.chloe_common import data_source
from chloe.chloe_common.common_udf import get_str,get_bigint,get_int,get_float
from pyflink.table.expressions import col,lit,concat_ws,if_then_else
from pyflink.table import *

"""
单件素材报表
"""

dataSource = None


@udtf(input_types=[DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING()],
      result_types=[DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING(), DataTypes.STRING()])
def split_item_id(typeid, subtypeid, itemids, subitemid, jcnuserid):
    if itemids != '':
        itemList = itemids.split(",")
        for itemid in itemList:
            yield subtypeid, itemid, subitemid, jcnuserid, typeid


@udf(input_types=[DataTypes.STRING()], result_type=DataTypes.ROW())
def split_collocation_data_obj(dataObj):
   data = json.loads(dataObj)
   collocationId = data.get('collocationId',-1)
   userId = data.get('userId',-1)
   source = data.get('source',-1)
   return {"item_id":collocationId,"user_id":userId,"source":str(source)}


def main(date):
    env_settings = EnvironmentSettings.new_instance().use_blink_planner().in_batch_mode().build()
    st_env = BatchTableEnvironment.create(environment_settings=env_settings)
    st_env.get_config().get_configuration().set_boolean('python.fn-execution.memory.managed', True)
    st_env.add_python_archive('/space/flink/conda.zip')
    st_env.get_config().set_python_executable('conda.zip/conda/bin/python')

    hive_catalog = HiveCatalog("myhive", "chloe", "/space/flink/hive-conf")
    st_env.register_catalog("myhive", hive_catalog)
    st_env.use_catalog("myhive")
    st_env.use_database("chloe")

    st_env.create_temporary_function('split_item_id', split_item_id)
    st_env.create_temporary_function('split_collocation_data_obj', split_collocation_data_obj)
    st_env.create_temporary_function('get_str', get_str)
    st_env.create_temporary_function('get_int', get_int)
    st_env.create_temporary_function('get_bigint', get_bigint)
    st_env.create_temporary_function('get_float', get_float)
    # drop or create table
    test_env = dataSource.get_chloe_db_env()

    createMaterialTable(test_env['host'], test_env['port'], test_env['db'], test_env['user'], test_env['passwd'],
                             st_env)

    # 套装信息
    sql = "SELECT a.id,a.gender FROM `face_shop_collocation` a WHERE a.status>=0"
    group_material_table = st_env.sql_query(sql)

    sql = "select typeid,subtypeid,itemid,subitemid, jcnuserid  from chloe_common_stats_log where ds='%s' and (typeid='collocation') and itemid<>'' " % date
    print('query sql is', sql)
    common_stats_result = st_env.sql_query(sql)
    common_all_stats_result = common_stats_result.join_lateral(split_item_id(common_stats_result.typeid,common_stats_result.subtypeid,common_stats_result.itemid,common_stats_result.subitemid,common_stats_result.jcnuserid).alias('a','b','c','d','e')).select(col('a').alias('subtypeid'),col('b').cast(DataTypes.BIGINT()).alias('itemid'),col('c').alias('subitemid'),col('d').alias('jcnuserid'),col('e').alias('typeid'))

    # join合同两个表 subtypeid 表示点击/展示/保存类型，subitemid 表示来源是个人中心/新手流程
    material_full_table = common_all_stats_result.join(group_material_table,common_all_stats_result.itemid == group_material_table.id).select(common_all_stats_result.subtypeid,common_all_stats_result.subitemid.alias('source'),group_material_table.gender,common_all_stats_result.jcnuserid)

    # 查询购买信息
    sql2 = "select ds, bustype,dataobj from chloe_bus_hive_log where ds='%s' and (bustype=12) " % date
    origin_result = st_env.sql_query(sql2)
    #格式化数据
    purchase_group_full_table = origin_result.select(split_collocation_data_obj(origin_result.dataobj).alias('rs')).select(
        get_bigint(col('rs'),'item_id').alias('item_id'),get_bigint(col('rs'),'user_id').alias('user_id') ,get_str(col('rs'),'source').alias('source'))
    #维表联查，补充记录的性别信息
    purchase_full_table = purchase_group_full_table.join(group_material_table, purchase_group_full_table.item_id == group_material_table.id).select(purchase_group_full_table.source,group_material_table.gender,purchase_group_full_table.user_id)


    # 构造group by的字符串,key,source,gender,name分组
    group_key_str = "concat_ws('_',source, gender.cast(STRING))"
    result1 = dealDiffGroupBy(group_key_str, material_full_table, purchase_full_table)

    gender = "'-1'"
    source = 'source'
    group_key_str = "concat_ws('_',%s, %s.cast(STRING))" % ( source, gender)
    result2 = dealDiffGroupBy(group_key_str, material_full_table, purchase_full_table)

    gender = "gender"
    source = "'-1'"
    group_key_str = "concat_ws('_',%s, %s.cast(STRING))" % ( source, gender)
    result3 = dealDiffGroupBy(group_key_str, material_full_table, purchase_full_table)


    gender = "'-1'"
    source = "'-1'"
    group_key_str = "concat_ws('_',%s, %s.cast(STRING))" % ( source, gender)
    result4 = dealDiffGroupBy(group_key_str, material_full_table, purchase_full_table)


    result = result1.union_all(result2)
    result = result.union_all(result3)
    result = result.union_all(result4)
    result.execute().print()

def dealDiffGroupBy(group_key_str, material_full_table, purchase_full_table):

    material_full_table = material_full_table.select(group_key_str+" as group_key, subtypeid,jcnuserid")

    # key,subitemid,gender,name 分组后的结果
    group_result = material_full_table.group_by(material_full_table.group_key,material_full_table.subtypeid).select(material_full_table.group_key,material_full_table.subtypeid,material_full_table.jcnuserid.count.alias('pv'),material_full_table.jcnuserid.count.distinct.alias('uv'))
    show_result = group_result.where(group_result.subtypeid == 'materialShow').select(group_result.group_key.alias('show_group_key'),group_result.pv.alias('show_pv'),group_result.uv.alias('show_uv'))
    click_result = group_result.where(group_result.subtypeid == 'materialClick').select(group_result.group_key.alias('click_group_key'),group_result.pv.alias('click_pv'),group_result.uv.alias('click_uv'))
    save_result = group_result.where(group_result.subtypeid == 'materialSave').select(group_result.group_key.alias('save_group_key'),group_result.pv.alias('save_pv'),group_result.uv.alias('save_uv'))
    #join
    result = show_result.left_outer_join(click_result, show_result.show_group_key==click_result.click_group_key).select(show_result.show_group_key,show_result.show_pv,show_result.show_uv, if_then_else(click_result.click_pv.is_null,lit('0').cast(DataTypes.BIGINT()), click_result.click_pv).alias('click_pv'),if_then_else(click_result.click_uv.is_null,lit('0').cast(DataTypes.BIGINT()), click_result.click_uv).alias('click_uv'))

    result = result.left_outer_join(save_result, result.show_group_key==save_result.save_group_key).select(result.show_group_key,result.show_pv,result.show_uv,result.click_pv,result.click_uv,if_then_else(save_result.save_pv.is_null,lit('0').cast(DataTypes.BIGINT()), save_result.save_pv).alias('save_pv'),if_then_else(save_result.save_uv.is_null,lit('0').cast(DataTypes.BIGINT()), save_result.save_uv).alias('save_uv'))

    # 购买group by后的结果
    purchase_full_table = purchase_full_table.select(group_key_str+" as group_key, user_id")
    group_purchase_result = purchase_full_table.group_by(purchase_full_table.group_key).select(purchase_full_table.group_key.alias('purchase_group_key'),purchase_full_table.user_id.count.alias('purchase_pv') ,purchase_full_table.user_id.count.distinct.alias('purchase_uv'))
    result = result.left_outer_join(group_purchase_result, result.show_group_key==group_purchase_result.purchase_group_key).select(result.show_group_key,result.show_pv,result.show_uv,result.click_pv,result.click_uv,result.save_pv,result.save_uv,if_then_else(group_purchase_result.purchase_pv.is_null,lit('0').cast(DataTypes.BIGINT()), group_purchase_result.purchase_pv).alias('purchase_pv'),if_then_else(group_purchase_result.purchase_uv.is_null,lit('0').cast(DataTypes.BIGINT()), group_purchase_result.purchase_uv).alias('purchase_uv'))
    return result


def createMaterialTable(host, port, db, username, password, st_env):
    st_env.execute_sql("DROP TABLE IF EXISTS face_shop_collocation")
    sql = """
        CREATE TABLE `face_shop_collocation` (
          `id` BIGINT,
          `gender` INT,
          `status` INT,
          PRIMARY KEY (`id`) NOT ENFORCED
        ) WITH (
           'connector' = 'jdbc',
           'url' = 'jdbc:mysql://%s:%s/%s?useUnicode=true&characterEncoding=UTF-8',
           'table-name' = 'face_shop_collocation',
           'username' = '%s',
           'password' = '%s'
        )
    """ % (host, port, db, username, password)
    st_env.execute_sql(sql)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--date')
    parser.add_argument('--env')
    args = parser.parse_args()
    env = args.env
    dataSource = data_source.DataSource(env)
    date = args.date
    main(date)