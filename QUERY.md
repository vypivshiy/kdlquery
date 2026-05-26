## синтаксис селекторов

```
// ─── Нода ───────────────────────────────────────────────
name                    // по имени
*                       // любая нода
(type)                  // по type annotation ноды
(type)name              // type + имя

// ─── Свойства ────────────────────────────────────────────
[key]                   // свойство существует
[key=val]               // значение равно val
[key^=val]              // начинается с
[key$=val]              // заканчивается на
[key~=val]              // содержит подстроку
[(type)key]             // свойство существует и его значение имеет type annotation
[(type)key=val]         // + значение равно val
[(type)key^=val]        // + начинается с
[(type)key$=val]        // + заканчивается на
[(type)key~=val]        // + содержит подстроку

// ─── Аргументы ───────────────────────────────────────────
[N]                     // аргумент на позиции N существует
[N=val]                 // аргумент[N] равен val
[N^=val]                // начинается с
[N$=val]                // заканчивается на
[N~=val]                // содержит подстроку
[(type)N]               // аргумент[N] существует и имеет type annotation
[(type)N=val]           // + значение равно val
[(type)N^=val]          // + начинается с
[(type)N$=val]          // + заканчивается на
[(type)N~=val]          // + содержит подстроку
[*=val]                 // любой аргумент равен val

// ─── Комбинаторы ─────────────────────────────────────────
A B                     // descendant
A > B                   // direct child
A + B                   // adjacent sibling
A ~ B                   // general sibling

// ─── Псевдоклассы ────────────────────────────────────────
:root
:first-child
:last-child
:nth-child(n)
:nth-child(2n)
:nth-child(2n+1)
:only-child
:empty
```

---

### Тестовый KDL 2.0 документ

```kdl
/- kdl-version 2

app "my-service" version="1.0.0" {
    (network)server "primary" port=8080 tls=#true {
        host "localhost"
        host "127.0.0.1"
        timeout idle=30 connect=5
    }

    (network)server "replica" port=8081 tls=#false {
        host "replica.local"
        timeout idle=60 connect=5
    }

    router {
        route "GET" "/api/users" handler="users.list" auth=#true
        route "POST" "/api/users" handler="users.create" auth=#true
        route "GET" "/api/health" handler="health.check" auth=#false
        route "GET" "/static/*" handler="static.serve" auth=#false
    }

    plugins {
        plugin "auth" enabled=#true {
            (jwt)secret "hs256" key=(regex)"hs(256|512)"
            expires (i32)3600
        }
        plugin "cache" enabled=#true {
            backend "redis" host="cache.local" port=(u16)6379
        }
        plugin "debug" enabled=#false
    }

    (i32)workers 4
    (i32)timeout 30
    limits max-conn=(u32)1000 max-req=(u32)500
}
```

Ключевые добавления по сравнению с прошлой версией:
- `(jwt)secret` — type annotation на ноде + `key=(regex)"..."` — на свойстве
- `expires (i32)3600` — type annotation на аргументе
- `port=(u16)6379` — type annotation на свойстве
- `limits` с `(u32)` на двух свойствах

---

### Test cases

#### Нода по имени и wildcard

```
app
// → [app]

server
// → [server "primary", server "replica"]

*:root
// → [app]
```

---

#### Type annotation на ноде

```
(network)
// → [server "primary", server "replica"]

(network)server
// → [server "primary", server "replica"]

(i32)
// → [workers 4, timeout 30]

(i32)workers
// → [workers 4]

(jwt)
// → [secret "hs256"]

(jwt)secret
// → [secret "hs256"]
```

---

#### Свойства — базовые

```
server[tls]
// → [server "primary", server "replica"]

server[tls=#true]
// → [server "primary"]

server[tls=#false]
// → [server "replica"]

server[port=8080]
// → [server "primary"]

route[auth=#true]
// → [route "GET" "/api/users", route "POST" "/api/users"]

route[handler^="users"]
// → [route "GET" "/api/users", route "POST" "/api/users"]

route[handler$="check"]
// → [route "GET" "/api/health"]

route[handler~="serve"]
// → [route "GET" "/static/*"]

app[version]
// → [app]

app[version="1.0.0"]
// → [app]
```

---

#### Свойства — type annotation на значении

```
[(u16)port]
// → [backend "redis"]

backend[(u16)port]
// → [backend "redis"]

backend[(u16)port=6379]
// → [backend "redis"]

[(u32)max-conn]
// → [limits]

limits[(u32)max-conn]
// → [limits]

limits[(u32)max-conn=1000]
// → [limits]

limits[(u32)max-req=500]
// → [limits]

[(regex)key]
// → [secret "hs256"]

secret[(regex)key]
// → [secret "hs256"]

secret[(regex)key~="hs"]
// → [secret "hs256"]

// type не совпадает — пустой результат
backend[(u32)port]
// → []

secret[(jwt)key]
// → []
```

---

#### Аргументы — базовые

```
server[0]
// → [server "primary", server "replica"]

server[0="primary"]
// → [server "primary"]

server[0="replica"]
// → [server "replica"]

route[0="GET"]
// → [route "GET" "/api/users", route "GET" "/api/health", route "GET" "/static/*"]

route[1="/api/users"]
// → [route "GET" "/api/users", route "POST" "/api/users"]

route[1^="/api"]
// → [route "GET" "/api/users", route "POST" "/api/users", route "GET" "/api/health"]

route[1^="/static"]
// → [route "GET" "/static/*"]

route[1$="/users"]
// → [route "GET" "/api/users", route "POST" "/api/users"]

route[1~="health"]
// → [route "GET" "/api/health"]

route[*="POST"]
// → [route "POST" "/api/users"]

plugin[0]
// → [plugin "auth", plugin "cache", plugin "debug"]

plugin[1]
// → []
```

---

#### Аргументы — type annotation на значении

```
expires[(i32)0]
// → [expires 3600]

expires[(i32)0=3600]
// → [expires 3600]

// тип не совпадает
expires[(u32)0]
// → []

// нода с аргументом[0] с type annotation (i32)
(i32)workers[(i32)0]
// → []  — у workers нет аргументов с type annotation, само число 4 без аннотации

// аргумент с любым типом i32 в позиции 0
*[(i32)0]
// → [expires 3600]
```

---

#### Комбинаторы

```
app > server
// → [server "primary", server "replica"]

app > router > route
// → все четыре route

app > route
// → []

plugins > plugin
// → [plugin "auth", plugin "cache", plugin "debug"]

plugin > backend
// → [backend "redis"]

(network)server[tls=#true] > host
// → [host "localhost", host "127.0.0.1"]

(network)server[tls=#false] > host
// → [host "replica.local"]

app server
// → [server "primary", server "replica"]

app route
// → все четыре route

plugins plugin[enabled=#true] > backend
// → [backend "redis"]
```

---

#### Siblings

```
route[0="GET"] + route
// → [route "POST" "/api/users", route "GET" "/static/*"]

route[0="POST"] + route
// → [route "GET" "/api/health"]

route[0="GET"][1$="/users"] ~ route
// → [route "POST" "/api/users", route "GET" "/api/health", route "GET" "/static/*"]

plugin[0="auth"] + plugin
// → [plugin "cache"]

plugin[0="auth"] ~ plugin
// → [plugin "cache", plugin "debug"]

plugin[0="debug"] + plugin
// → []
```

---

#### Псевдоклассы

```
route:first-child
// → [route "GET" "/api/users"]

route:last-child
// → [route "GET" "/static/*"]

route:nth-child(2)
// → [route "POST" "/api/users"]

route:nth-child(2n)
// → [route "POST" "/api/users", route "GET" "/static/*"]

route:nth-child(2n+1)
// → [route "GET" "/api/users", route "GET" "/api/health"]

plugin:only-child
// → []

host:only-child
// → [host "replica.local"]

plugin[0="debug"]:last-child
// → [plugin "debug"]

plugin[0="debug"]:empty
// → [plugin "debug"]

backend:empty
// → [backend "redis"]

expires:empty
// → [expires 3600]

server:first-child
// → [server "primary"]

(i32):last-child
// → [timeout 30]

app:root
// → [app]

server:root
// → []
```

---

#### Комбинированные — для регрессий

```
// type на ноде + фильтр по свойству + descendant
(network)server[tls=#true] host
// → [host "localhost", host "127.0.0.1"]

// type на свойстве + комбинатор
app > *[(u32)max-conn]
// → [limits]

// type на аргументе + псевдокласс
*[(i32)0]:empty
// → [expires 3600]

// несколько атрибутных фильтров
route[auth=#false][0="GET"]
// → [route "GET" "/api/health", route "GET" "/static/*"]

// type annotation на ноде + атрибут с type annotation на значении
(jwt)secret[(regex)key]
// → [secret "hs256"]

// цепочка descendant + type annotation на свойстве
plugins plugin[(u16)port]
// → []  — port с типом u16 у backend, не у plugin напрямую

app backend[(u16)port]
// → [backend "redis"]
```