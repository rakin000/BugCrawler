# DISPATCH-37

### Link

https://issues.apache.org/jira/browse/DISPATCH-37

### Bug category

​		memory leaks

### Bug trigger

​	Very basic usage of Dispatch router. 

​	 For basic scenario, have 2 routers A<->B and send messages from bouncing producer connected to A to a bouncing consumer connected to B.

​	By connecting and disconnecting another router to an inter-router listener:

### Root cause

Playing with the scenarios and debugfging the leaks, it seems like freeing almost any object forgets to free "nested" objects it encapsulates. **E.g.** when dropping a connection, qd_dealloc is called to qd_connection_t but is not called within it for qd_link_t for any link on that connection.

	几乎所有对象在释放（free）的时候，都会忘记释放它所封装（包含）的“嵌套”对象。

 比如，当释放一个连接（connection）时，虽然调用了 `qd_dealloc` 去释放 `qd_connection_t`，但并没有在这个过程中去释放该连接下的所有 `qd_link_t`（即连接所持有的链接对象）。	

### Consequence

​	memory leaks from a minute run

### Fix

​	https://svn.apache.org/r1596682

### Log

​	**7696** lines in total

### LLM prompt

#### Question 1:

​	The following are logs from Qpid Dispatch.

Do you find any evidence of a calling relationship between processes?

 \- Say ‘YES:{functions/processes}’ if you detect a relationship in the log

 \- Say ‘NO:{INDEX}’ if there is no relationship

\- Say ‘Unsure if you need more details or context’

#### Answer 1:

<img src="/Users/qwb/Library/Application Support/typora-user-images/image-20250326204129786.png" alt="image-20250326204129786" style="zoom:50%;" />

​	**YES: {QDR.01 ↔ QDR.02, qd_add_neighbor_router → qd_add_remote_router → qd_del_neighbor_router → qd_del_router}**

从日志中可以明确看到存在 **调用关系和通信过程**，说明存在 **进程间（或组件间）的交互关系**。以下是相关证据：

### 🔗 路由器间的邻居关系（QDR.01 ↔ QDR.02）

```
CopyEdit
Thu Mar 27 12:33:32 dispatch.router (DEBUG) Event: new_neighbor: id=QDR.02 link_id=0
Thu Mar 27 12:33:32 dispatch.router (DEBUG) Event: add_neighbor_router: address=amqp:/_topo/0/QDR.02, router_bit=1, link_bit=0
Thu Mar 27 12:33:34 dispatch.router (INFO) Learned link-state from new router: QDR.02
Thu Mar 27 12:34:06 dispatch.router (INFO) Neighbor lost: QDR.02
```

✅ 说明 QDR.01 和 QDR.02 之间建立了 **邻居关系**（neighbor relationship），存在交互与消息同步。

------

### 🧩 函数调用链（从 Valgrind 报告中）

Valgrind 日志中记录了如下函数调用关系，表明内部模块之间存在明确调用路径：

```
CopyEdit
qd_add_neighbor_router
 → qd_add_remote_router
   → qd_router_register_address
     → qd_router
       → qd_dispatch_prepare
         → main
```

同时还有：

```
CopyEdit
qd_del_neighbor_router
 → qd_del_router
```

✅ 表示在邻居断开时，清理路由状态的函数链被触发，**显示出函数之间有明确的调用关系**。

------

### 📌 所以结论是：

**YES: {QDR.01 ↔ QDR.02, qd_add_neighbor_router → qd_add_remote_router → qd_router_register_address → qd_router, qd_del_neighbor_router → qd_del_router}**

如你需要进一步分析哪些函数调用哪些对象释放逻辑等，也可以继续深入 Valgrind 报告。需要我帮你提取函数调用图或者对象间的释放逻辑吗？

····································································································································································································································································································································

#### Question 2:

​	Do you find any evidence that two processes you mentioned have memory leak issue? 

​	\- Say ‘YES:{LOG INDEX}’ if you detect a memory leak issue corresponding to these two processed.

​	\- Say ‘NO:{INDEX}’ if there is no memory leak issue

​	- Say ‘Unsure if you need more details or context’

#### Answer 2:

<img src="/Users/qwb/Library/Application Support/typora-user-images/image-20250326204805839.png" alt="image-20250326204805839" style="zoom:50%;" />

**YES: {Valgrind log – memory leak related to QDR.01 and QDR.02 interaction}**

### 📌 证据说明：

在 Valgrind 输出中，存在以下记录，显示在处理邻居路由器（如 QDR.02）相关逻辑时，有 **明确的内存泄漏问题**：

#### 示例 1（涉及 `qd_add_remote_router`）：

```
CopyEdit
==2761== 8 bytes in 1 blocks are possibly lost in loss record 20 of 2,684
==2761==    by 0x4C26100: qd_hash_internal_insert
==2761==    by 0x4C262F2: qd_hash_insert
==2761==    by 0x4C329CA: qd_add_router
==2761==    by 0x4C330D8: qd_add_remote_router
```

该路径与邻居 QDR.02 的注册密切相关（根据日志：`add_neighbor_router`, `add_remote_router`）。

------

#### 示例 2（涉及邻居路由器的释放）：

```
CopyEdit
==2761== 32 bytes in 1 blocks are definitely lost in loss record 351 of 2,684
==2761==    by 0x4C20588: qd_dealloc
==2761==    by 0x4C2D945: free_qd_router_ref_t
==2761==    by 0x4C2DF83: qd_router_del_node_ref_LH
==2761==    by 0x4C32DBF: qd_del_router
==2761==    by 0x4C33716: qd_del_neighbor_router
```

这显示在邻居 QDR.02 **断开连接或移除时**，有路由器引用未被正确释放。

------

### 🔍 所以结论是：

**YES: {Valgrind log blocks 20, 351, others involving qd_add_remote_router and qd_del_neighbor_router}**

这些泄漏与 QDR.01 与 QDR.02 之间的动态邻居关系（建立与断开）直接相关，说明它们的交互确实引发了内存泄漏。

是否需要我汇总所有相关函数栈和泄漏字节数做个表格？

····································································································································································································································································································································

#### Question 3:

​	If you confirm two processes you mentioned have memory leak issue, could you deduce the root cause of this memory leak issue?

​	\- Say ‘YES:{LOG INDEX}’ if you deduce the root cause corresponding to the log content.

​	\- Say ‘NO:{INDEX}’ if you can not deduce the root cause.

​	- Say ‘Unsure if you need more details or context’.

#### Answer 3:

<img src="/Users/qwb/Library/Application Support/typora-user-images/image-20250326205248281.png" alt="image-20250326205248281" style="zoom: 33%;" />

**YES: {Valgrind log blocks 351, 20, 22, 253}**

------

### 📌 **可推导的内存泄漏根因（Root Cause）**：

根据日志内容和函数调用栈，可以**明确推断出一些内存泄漏的根本原因**，尤其是在处理邻居路由器 QDR.02 的生命周期时：

------

### ✅ 泄漏根因 #1：**邻居移除时未彻底释放嵌套对象**

**Log Index: 351**

```
CopyEdit
==2761== 32 bytes in 1 blocks are definitely lost in loss record 351 of 2,684
==2761==    by 0x4C20588: qd_dealloc
==2761==    by 0x4C2D945: free_qd_router_ref_t
==2761==    by 0x4C2DF83: qd_router_del_node_ref_LH
==2761==    by 0x4C32DBF: qd_del_router
==2761==    by 0x4C33716: qd_del_neighbor_router
```

💡 推论：`qd_del_neighbor_router` 被调用时，**只是释放了部分结构体（如引用计数），但它内部嵌套的路由引用（`qd_router_ref_t`）等未被彻底递归释放**。

------

### ✅ 泄漏根因 #2：**hash 插入但未释放字段迭代器**

**Log Index: 20**

```
CopyEdit
==2761== 8 bytes in 1 blocks are possibly lost in loss record 20 of 2,684
==2761==    by 0x4C2761D: qd_field_iterator_copy
==2761==    by 0x4C26100: qd_hash_internal_insert
==2761==    by 0x4C262F2: qd_hash_insert
==2761==    by 0x4C329CA: qd_add_router
```

💡 推论：在添加邻居路由器 `qd_add_router` 时，调用了 `qd_hash_insert`，它创建了字段拷贝（`qd_field_iterator_copy`），但**没有在结构销毁时释放这部分动态分配的内存**。

------

### ✅ 泄漏根因 #3：**配置处理后未清理字符串拷贝**

**Log Index: 22**

```
CopyEdit
==2761== 9 bytes in 1 blocks are definitely lost
==2761==    by 0x4C232C7: qd_config_item_value_string
==2761==    by 0x4C25467: qd_dispatch_configure_router
```

💡 推论：配置阶段分配的字符串值，在后续使用完后未被释放（如配置解析后的临时对象、item-value），**导致小块字符串泄漏**。

------

### ✅ 泄漏根因 #4：**日志模块注册信息未释放**

**Log Index: 253**

```
CopyEdit
==2761== 24 bytes in 1 blocks are definitely lost in loss record 253 of 2,684
==2761==    by 0x4C27978: qd_log_source
==2761==    by 0x4C31A99: qd_router
```

💡 推论：日志源 `qd_log_source` 在调用过程中为每个模块分配了内存（如 router），但该内存未在 shutdown 时正确释放。

------

### ✅ 综合推理：

大部分内存泄漏是由于：

1. **嵌套结构的释放不完整**（未递归释放子对象）。
2. **动态配置/拷贝生命周期不清晰**。
3. **模块初始化时的注册信息未被正确清理**。

------

### ✅ 结论：

**YES: {351, 20, 22, 253}**

我们已经可以从日志中清晰推导出泄漏的根因。如果你需要我帮你整理函数调用路径图，或建议修复策略，也可以继续提出。

### Comparison experiment