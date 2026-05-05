-- ============================================
-- RailMind AI - MySQL Database Schema
-- Howrah to Jakpur Corridor
-- ============================================

CREATE DATABASE IF NOT EXISTS railmind_db_2;
USE railmind_db_2;

-- Drop tables if exist (for clean reinstall)
DROP TABLE IF EXISTS train_movements;
DROP TABLE IF EXISTS trains_data;
DROP TABLE IF EXISTS blocks_data;

-- ============================================
-- Table 1: blocks_data
-- ============================================
CREATE TABLE blocks_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Block_ID VARCHAR(10) NOT NULL UNIQUE,
    From_point VARCHAR(100) NOT NULL,
    To_point VARCHAR(100) NOT NULL,
    Block_length_km INT NOT NULL,
    Line_type VARCHAR(10) NOT NULL,
    Has_loop_line INT DEFAULT 0,
    Loop_capacity INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_block_id (Block_ID),
    INDEX idx_line_type (Line_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Table 2: trains_data
-- ============================================
CREATE TABLE trains_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Train_ID INT NOT NULL UNIQUE,
    Train_name VARCHAR(150) NOT NULL,
    Train_type VARCHAR(50) NOT NULL,
    Priority_level INT NOT NULL,
    Direction VARCHAR(10) NOT NULL,
    Train_avg_speed_kmph INT DEFAULT 60,
    Max_dwell_time_min INT DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_train_id (Train_ID),
    INDEX idx_train_type (Train_type),
    INDEX idx_priority (Priority_level),
    INDEX idx_direction (Direction)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Table 3: train_movements
-- ============================================
CREATE TABLE train_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Train_ID INT NOT NULL,
    Block_id VARCHAR(10) NOT NULL,
    Delay_at_entry_min INT DEFAULT 0,
    Delay_at_exit_min INT DEFAULT 0,
    Block_occupied_flag INT DEFAULT 0,
    Conflict_flag INT DEFAULT 0,
    Action_taken VARCHAR(50) DEFAULT 'PROCEED',
    Remarks VARCHAR(255) DEFAULT NULL,
    Scheduled_Arrival_Time VARCHAR(20) NOT NULL,
    Actual_Arrival_Time VARCHAR(20) NOT NULL,
    Train_Status_When_Arrived VARCHAR(20) DEFAULT 'On Time',
    Scheduled_Departure_Time VARCHAR(20) NOT NULL,
    Actual_Departure_Time VARCHAR(20) NOT NULL,
    Train_status_when_departed VARCHAR(20) DEFAULT 'On Time',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_train_id (Train_ID),
    INDEX idx_block_id (Block_id),
    INDEX idx_conflict (Conflict_flag),
    INDEX idx_delay_entry (Delay_at_entry_min),
    
    FOREIGN KEY (Train_ID) REFERENCES trains_data(Train_ID) ON DELETE CASCADE,
    FOREIGN KEY (Block_id) REFERENCES blocks_data(Block_ID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- Verify tables created
-- ============================================
SHOW TABLES;
