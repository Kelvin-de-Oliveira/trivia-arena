package com.trivia.game.config;

import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

@Configuration
public class DataSourceConfiguration {
    @Bean("shardADataSource")
    @ConfigurationProperties("game.datasource.shard-a")
    DataSource shardADataSource() {
        return DataSourceBuilder.create().type(HikariDataSource.class).build();
    }

    @Bean("shardBDataSource")
    @ConfigurationProperties("game.datasource.shard-b")
    DataSource shardBDataSource() {
        return DataSourceBuilder.create().type(HikariDataSource.class).build();
    }

    @Bean("shardAJdbcTemplate")
    JdbcTemplate shardAJdbcTemplate(@Qualifier("shardADataSource") DataSource shardADataSource) {
        return new JdbcTemplate(shardADataSource);
    }

    @Bean("shardBJdbcTemplate")
    JdbcTemplate shardBJdbcTemplate(@Qualifier("shardBDataSource") DataSource shardBDataSource) {
        return new JdbcTemplate(shardBDataSource);
    }
}
