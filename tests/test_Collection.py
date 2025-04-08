import pytest
import sys

sys.path.append('../')

from pi.collection import Collection
from pi.MPRLS import MockPressureSensorStatic

class MockTank:
    """Mock Tank class to test Collection without real dependencies."""
    def __init__(self, name, pressure=50):
        self.name = name
        self.state = "CLOSED"
        self.pressure_sensor = MockPressureSensorStatic(pressure)

    def open(self):
        self.state = "OPEN"

    def close(self):
        self.state = "CLOSED"

@pytest.fixture
def mock_tank() -> MockTank:
    """Fixture for a mocked tank."""
    return MockTank("Mock Tank")

def test_collection_initialization():
    """Test that a collection initializes correctly with expected attributes."""
    collection = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        choke_pressure=1500.0,
        up_duration=600
    )

    assert collection.num == "1"
    assert collection.up_start_time == 40305
    assert collection.bleed_duration == 1
    assert collection.up_driving_pressure == 1270.44
    assert collection.p_choke == 1500.0
    assert collection.up_duration == 600
    assert collection.tank is None
    assert collection.pressure_sensor is None # Should be None when no tank is assigned
    assert collection.sampled is False
    assert collection.sampled_count == 0
    
    # Ensure old values no longer exist
    with pytest.raises(AttributeError):
        collection.down_start_time
    with pytest.raises(AttributeError):
        collection.down_driving_pressure
    with pytest.raises(AttributeError):
        collection.upwards_bleed
    with pytest.raises(AttributeError):
        collection.sample_upwards

def test_collection_associate_tank(mock_tank: MockTank):
    """Test associating a tank with a collection."""
    collection = Collection(
        num=2,
        up_start_time=70000,
        bleed_duration=5,
        up_driving_pressure=753.43,
        choke_pressure=500.0,
        up_duration=700
    )

    collection.associate_tank(mock_tank)

    assert collection.tank == mock_tank
    assert collection.pressure_sensor == mock_tank.pressure_sensor  # Ensure mprls is dynamically referenced

def test_collection_associate_tank_updates_properly(mock_tank: MockTank):
    """Test re-associating a different tank and sensor with a collection."""
    collection = Collection(
        num=3,
        up_start_time=90000,
        bleed_duration=36,
        up_driving_pressure=490.13,
        choke_pressure=300.0,
        up_duration=900
    )

    # First association
    collection.associate_tank(mock_tank)
    assert collection.tank == mock_tank
    assert collection.pressure_sensor == mock_tank.pressure_sensor

    # Change association
    new_tank = MockTank("New Tank", pressure=150)
    collection.associate_tank(new_tank)

    assert collection.tank == new_tank
    assert collection.pressure_sensor == new_tank.pressure_sensor
    assert collection.pressure_sensor.pressure == 150
    
def test_collections_in_array():
    """Verify handling of collection changes in an array."""

    collection1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        choke_pressure=1500.0,
        up_duration=600
    )
    
    collection2 = Collection(
        num=2,
        up_start_time=70000,
        bleed_duration=5,
        up_driving_pressure=753.43,
        choke_pressure=500.0,
        up_duration=700
    )
    
    collection3 = Collection(
        num=3,
        up_start_time=90000,
        bleed_duration=36,
        up_driving_pressure=490.13,
        choke_pressure=300.0,
        up_duration=900
    )

    tank1 = MockTank("Mock Tank 1", pressure=100)
    tank2 = MockTank("Mock Tank 2", pressure=200)
    tank3 = MockTank("Mock Tank 3", pressure=300)
    
    collection1.associate_tank(tank1)
    collection2.associate_tank(tank2)
    collection3.associate_tank(tank3)

    # Create an array of all our collections
    collections = [collection1, collection2, collection3]
    
    # Modify the base collections, simulating
    collection1.associate_tank(tank3)
    collection3.associate_tank(tank1)
    
    assert collections[0].tank == tank3
    assert collections[2].tank == tank1
    assert collections[0].pressure_sensor.pressure == 300
    assert collections[2].pressure_sensor.pressure == 100

def test_collection_swap_tanks():
    """Verify handling of collection changes in an array."""

    collection1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        choke_pressure=1500.0,
        up_duration=600
    )
    
    collection2 = Collection(
        num=2,
        up_start_time=70000,
        bleed_duration=5,
        up_driving_pressure=753.43,
        choke_pressure=500.0,
        up_duration=700
    )

    tank1 = MockTank("Mock Tank 1", pressure=100)
    tank2 = MockTank("Mock Tank 2", pressure=200)
    
    collection1.associate_tank(tank1)
    collection2.associate_tank(tank2)

    # Create an array of all our collections
    collections = [collection1, collection2]
    
    # Modify the base collections, simulating
    Collection.swap_tanks(collections[0], collections[1])
    
    assert collection1.tank == tank2
    assert collection2.tank == tank1

    assert collections[0].tank == tank2
    assert collections[1].tank == tank1
    assert collections[0].pressure_sensor.pressure == 200
    assert collections[1].pressure_sensor.pressure == 100