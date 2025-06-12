brRedis Anti-Patterns Every Developer Should Avoid
Ajeet Raina
Author
Ajeet Raina, Former Developer Growth Manager at Redis

Developers don’t just use Redis, they love it. Stack Overflow’s annual Developer Survey 2021 has ranked Redis as the Most Loved Database platform for the fifth years running! But it is equally important to understand that Redis defaults are not the best for everyone. Millions of developers uses Redis due to its speed and performance, however it is important to make sure that it is being used properly.

"Antipatterns" basically refers to those practices and solutions that might seem to be a good fit initially but when it comes to implementation phase, it makes your code much more complex. Let us look at the top Redis anti-patterns to avoid:

1. Large databases running on a single shard/Redis instance#

With large databases running on a single shard/Redis instance, there are chances that the fail over, backup and recovery all will take longer. Hence, it’s always recommended to keep shards to recommended sizes. General conservative rule of thumb is 25Gb or 25K Ops/Second.

Redis Cloud recommends to shard if you have more than 25 GB of data and a high number of operations. Another aspect is if you have above 25,000 operations per second, then sharding can improve performance. With less number of operations/second, it can handle up to 50GB of data too.
Examples #1 - redis-py#

Let us look at the redis-py that uses a connection pool to manage connections to a Redis server. By default, each Redis instance you create will in turn create its own connection pool. You can override this behavior and use an existing connection pool by passing an already created connection pool instance to the connection_pool argument of the Redis class. You may choose to do this in order to implement client side sharding or have fine-grain control of how connections are managed.

> > > pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
> > > r = redis.Redis(connection_pool=pool)

2. Connecting directly to Redis instances#

With a large number of clients, a reconnect flood will be able to simply overwhelm a single threaded Redis process and force a failover. Hence, it is recommended that you should use the right tool that allows you to reduce the number of open connections to your Redis server.

Redis Enterprise DMC proxy allows you to reduce the number of connections to your cache server by acting as a proxy. There are other 3rd party tool like Twemproxy. It is a fast and lightweight proxy server that allows you to reduce the number of open connections to your Redis server. It was built primarily to reduce the number of connections to the caching servers on the backend. This, together with protocol pipelining and sharding enables you to horizontally scale your distributed caching architecture. 3. More than one secondary shard (Redis OSS)#

Redis OSS uses a shard-based quorum. It's advised to use at least 3 copies of the data (2 replica shards per master shard) in order to be protected from split-brain situations. In nutshell, Redis OSS solves the quorum challenge by having an odd number of shards (primary + 2 replicas).

Redis Cloud solves the quorum challenge with an odd number of nodes. Redis Cloud avoids a split-brain situation with only 2 copies of the data, which is more cost-efficient. In addition, the so-called ‘quorum-only node' can be used to bring a cluster up to an odd number of nodes if an additional, not necessary data node would be too expensive. 4. Performing single operation#

Performing several operations serially increases connection overhead. Instead, use Redis Pipelining. Pipelining is the process of sending multiple messages down the pipe without waiting on the reply from each - and (typically) processing the replies later when they come in.

Pipelining is completely a client side implementation. It is aimed at solving response latency issues in high network latency environments. So, the lesser the amount of time spent over the network in sending commands and reading responses, the better. This is effectively achieved by buffering. The client may (or may not) buffer the commands at the TCP stack (as mentioned in other answers) before they are sent to the server. Once they are sent to the server, the server executes them and buffers them on the server side. The benefit of the pipelining is a drastically improved protocol performance. The speedup gained by pipelining ranges from a factor of five for connections to localhost up to a factor of at least one hundred over slower internet connections. 5. Caching keys without TTL#

Redis functions primarily as a key-value store. It is possible to set timeout values on these keys. Said that, a timeout expiration automatically deletes the key. Additionally, when we use commands that delete or overwrite the contents of the key, it will clear the timeout. Redis TTL command is used to get the remaining time of the key expiry in seconds. TTL returns the remaining time to live of a key that has a timeout. This introspection capability allows a Redis client to check how many seconds a given key will continue to be part of the dataset.Keys will accumulate and end up being evicted. Hence, it is recommended to set TTLs on all caching keys. 6. Endless Redis Replication Loop#

When attempting to replicate a very large active database over a slow or saturated link, replication never finishes due to the continuous updates. Hence, it is recommended to tune the slave and client buffers to allow for slower replication. Check out this detailed blog. 7. Hot Keys#

Redis can easily become the core of your app’s operational data, holding valuable and frequently accessed information. However, if you centralize the access down to a few pieces of data accessed constantly, you create what is known as a hot-key problem. In a Redis cluster, the key is actually what determines where in the cluster that data is stored. The data is stored in one single, primary location based off of hashing that key. So, when you access a single key over and over again, you’re actually accessing a single node/shard over and over again. Let’s put it another way—if you have a cluster of 99 nodes and you have a single key that gets a million requests in a second, all million of those requests will be going to a single node, not spread across the other 98 nodes.

Redis even provides tools to find where your hot keys are located. Use redis-cli with the –hotkeys argument alongside any other arguments you need to connect:

$ redis-cli --hotkeys

When possible, the best defence is to avoid the development pattern that is creating the situation. Writing the data to multiple keys that reside in different shards will allow you to access the same data more frequently. In nutshell, having specific keys that are accessed with every client operation. Hence, it's recommended to shard out hot keys using hashing algorithms. You can set policy to LFU and run redis-cli --hotkeys to determine. 8. Using Keys command#

In Redis, the KEYS command can be used to perform exhaustive pattern matching on all stored keys. This is not advisable, as running this on an instance with a large number of keys could take a long time to complete, and will slow down the Redis instance in the process. In the relational world, this is equivalent to running an unbound query (SELECT...FROM without a WHERE clause). Execute this type of operation with care, and take necessary measures to ensure that your tenants are not performing a KEYS operation from within their application code. Use SCAN, which spreads the iteration over many calls, not tying up your whole server at one time.

Scaning keyspace by keyname is an extremely slow operation and will run O(N) with N being the number of keys. It is recommended to use Redis Search to return information based on the contents of the data instead of iterating through the key space.

FT.SEARCH orders "@make: ford @model: explorer"
2SQL: SELECT \* FROM orders WHERE make=ford AND model=explorer"

9. Running Ephemeral Redis as a primary database#

Redis is often used as a primary storage engine for applications. Unlike using Redis as a cache, using Redis as a primary database requires two extra features to be effective. Any primary database should really be highly available. If a cache goes down, then generally your application is in a brown-out state. If a primary database goes down, your application also goes down. Similarly, if a cache goes down and you restart it empty, that’s no big deal. For a primary database, though, that’s a huge deal. Redis can handle these situations easily, but they generally require a different configuration than running as a cache. Redis as a primary database is great, but you’ve got to support it by turning on the right features.

With Redis open source, you need to set up Redis Sentinel for high availability. In Redis Cloud, it’s a core feature that you just need to turn on when creating the database. As for durability, both Redis Cloud and open source Redis provide durability through AOF or snapshotting so your instance(s) start back up the way you left them. 10. Storing JSON blobs in a string#

Microservices written in several languages may not marshal/unmarshal JSON in a consistent manner. Application logic will be required to lock/watch a key for atomic updates. JSON manipulation is often a very compute costly operation. Hence, it is recommended to use HASH data structure and also Redis JSON. 11. Translating a table or JSON to a HASH without considering query pattern#

The only query mechanism is a SCAN which requires reading the data structure and limits filtering to the MATCH directive. It is recommended to store the table or JSON as a string. Break out the indexes into reverse indexes using a SET or SORTED SET and point back to the key for the string. Using SELECT command and multiple databases inside one Redis instance

The usage of SELECT and multiple databases inside one Redis instance was mentioned as an anti-pattern by Salvatore (the creator of Redis). It is recommended to use a dedicated Redis instance for each database need. This is especially true in microservice architectures where client applications might step on each other's toes (noisy neighbor, database setup/teardown impact, maintenance, upgrade, ...)

The Redis Time Series module provides a direct compete to time series databases. But if the only query is based on ordering, it's unnecessary complexity. Hence, it is recommended to use a SORTED SET with a score of 0 for every value. The values are appended. Or use a timestamp for the score for simple time based queries
