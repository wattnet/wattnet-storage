# Changelog

## [1.1.0](https://github.com/wattnet/wattnet-storage/compare/v1.0.0...v1.1.0) (2026-06-07)


### Features

* add ClickHouse logs configuration to manage log retention and disable unnecessary logs ([8831278](https://github.com/wattnet/wattnet-storage/commit/8831278f9a652f0da298d3efad2fdc5cc5fdf995))
* add ClickHouse logs configuration to manage log retention and disable unnecessary logs ([d67e339](https://github.com/wattnet/wattnet-storage/commit/d67e339e3462f7ef3c0634f4021b65731de1934f))
* add CONTRIBUTING, SECURITY, and CODE OF CONDUCT documents; create issue templates for bug reports and feature requests ([148a7ca](https://github.com/wattnet/wattnet-storage/commit/148a7ca3e17d878ce54d8ab5ea1547124f4497c2))
* add LICENSE file with Apache License 2.0 details ([4347059](https://github.com/wattnet/wattnet-storage/commit/434705904c42ecbfecbbe1cce936cc7c1d0d39b7))
* add listen_host configuration to enforce IPv4 only ([8c04946](https://github.com/wattnet/wattnet-storage/commit/8c04946f8aecb76547697d0da9ba26306ba3370f))
* add listen_host configuration to enforce IPv4 only ([81411b1](https://github.com/wattnet/wattnet-storage/commit/81411b1741805ac3228edf09a71941d85defa747))
* add new metric types and update ClickHouse table schemas for zone load and impact metrics ([97aeeca](https://github.com/wattnet/wattnet-storage/commit/97aeeca7ef6a97238f528c81aaf259cc36cdb5d1))
* add zone_mix_generation schema and dashboard for generation and mix data ([018c825](https://github.com/wattnet/wattnet-storage/commit/018c82582051dd0f8962427f5ba24c9c201b870a))
* enhance ClickHouseClient with buffered writes and schema bootstrap ([49bc904](https://github.com/wattnet/wattnet-storage/commit/49bc904f56daf71540f447a48790daa6a4312634))
* enhance ClickHouseClient with buffered writes and schema bootstrap ([663385a](https://github.com/wattnet/wattnet-storage/commit/663385a911d066180d466b3946838fcdbdd49cf4))
* grafana dashboards with clickhouse database ([0b290bc](https://github.com/wattnet/wattnet-storage/commit/0b290bc4d0625cffb8dfc443d025032165b6860c))
* grafana dashboards with clickhouse database ([598ebe4](https://github.com/wattnet/wattnet-storage/commit/598ebe46d9b5c24c6b38a7f46421cd281ddd7b21))
* implement thread-local client storage in ClickHouseClient for concurrent queries ([2142355](https://github.com/wattnet/wattnet-storage/commit/2142355cf059c87831e8efe3dc470e34c71ffa8e))
* implement thread-local client storage in ClickHouseClient for concurrent queries ([279cc13](https://github.com/wattnet/wattnet-storage/commit/279cc13dd020bc63d5659cd00f3341048e9a6a94))
* implement time range resolution and refactor query building in ClickHouseClient ([ce4c0c4](https://github.com/wattnet/wattnet-storage/commit/ce4c0c4ba004cb4256da9a2634f291a66e90844c))
* Initialize wattnet-storage project with base structure and VictoriaMetrics client ([1dae3fd](https://github.com/wattnet/wattnet-storage/commit/1dae3fde25bc0995cab82813403ef67d10dadc5b))
* Replace VictoriaMetrics with ClickHouse as the storage backend … ([83c7339](https://github.com/wattnet/wattnet-storage/commit/83c73398fc696411eeb501db4b7a3824f471b964))
* Replace VictoriaMetrics with ClickHouse as the storage backend and update related configurations ([6378d0e](https://github.com/wattnet/wattnet-storage/commit/6378d0efe1e28cbcee210f15a58cfeb53c803fc7))
* update ClickHouse table schemas to use Float32 for value columns ([a7e9bc8](https://github.com/wattnet/wattnet-storage/commit/a7e9bc8264d269373c712f6f052d960a946cf766))
* update README with detailed storage backend and client library information; reorganize integration test docker-compose file ([e7cd4bd](https://github.com/wattnet/wattnet-storage/commit/e7cd4bdf9f4192b770ec88310604fd47d8348498))


### Bug Fixes

* Add timezone information to timestamp in ClickHouseClient ([5437dc4](https://github.com/wattnet/wattnet-storage/commit/5437dc4df18418978cd0b6d90bbc7a21143efb09))
* Add timezone information to timestamp in ClickHouseClient ([c9a4acb](https://github.com/wattnet/wattnet-storage/commit/c9a4acb0d0d4817904ee3c98411339448946437c))
* change lineInterpolation from linear to smooth in wattnet footprints dashboard ([c4eba99](https://github.com/wattnet/wattnet-storage/commit/c4eba99f50baaeaff088c8a2ccfde4e0224a6ad1))
* change lineInterpolation from linear to smooth in wattnet footprints dashboard ([32e796b](https://github.com/wattnet/wattnet-storage/commit/32e796b0e7437f25433a2be4bb63986bb93bd6e5))
* improve time range determination logic in ClickHouseClient ([7b23b5d](https://github.com/wattnet/wattnet-storage/commit/7b23b5d4b7bef76224513686df96469aa450364e))
* remove score_type column from local and global score table schemas ([c7ef06e](https://github.com/wattnet/wattnet-storage/commit/c7ef06e74f08e5688fe46ff680e101d22865d813))
* remove score_type column from local and global score table schemas ([123a691](https://github.com/wattnet/wattnet-storage/commit/123a69137587bc82c12c7faccd83879ca78ad93d))
* round metric values to two decimal places for consistency ([de33f92](https://github.com/wattnet/wattnet-storage/commit/de33f92764a05ec59598d331506ec276a8ad0bf5))
* update ClickHouse test service configuration for environment variables and volume path ([4d44819](https://github.com/wattnet/wattnet-storage/commit/4d44819d3b17056ee17ab068ffeccf37b26eb9f1))
* update Grafana dashboard IDs and plugin versions, and adjust SQL queries for final results ([c0d5e31](https://github.com/wattnet/wattnet-storage/commit/c0d5e311742358207ead1f8c3d731688b782cb12))
* update Grafana dashboard IDs and plugin versions, and adjust SQL queries for final results ([2d9b0c3](https://github.com/wattnet/wattnet-storage/commit/2d9b0c37b6e0b19361435d884ba61eab2ef4a838))
* update insertNulls value to 900000 in multiple Grafana dashboard JSON files (Disconnect values &gt; 15m) ([9456507](https://github.com/wattnet/wattnet-storage/commit/9456507bbf8970c21d8b08d20212d300cd006ef1))
* update insertNulls value to 900000 in multiple Grafana dashboard JSON files (Disconnect values &gt; 15m) ([88cfa3d](https://github.com/wattnet/wattnet-storage/commit/88cfa3d5a72b6cab1ae8b7551fc36e01fa264029))
* update project description for clarity and accuracy ([986ea4a](https://github.com/wattnet/wattnet-storage/commit/986ea4aa535f48d34bfc88572cd29ab92de27c33))
* update zone status options and queries in multiple Grafana dashboard JSON files ([523ce8c](https://github.com/wattnet/wattnet-storage/commit/523ce8cf60e8a19f58a9784a426beae7e30860d4))
