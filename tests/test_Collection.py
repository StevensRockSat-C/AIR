import pytest
import sys

sys.path.append('../')

from pi.collection import Collection

class MockTank:
    """Mock Tank class to test Collection without real dependencies."""
    def __init__(self, name, pressure=50):
        self.name = name
        self.state = "CLOSED"
        self.pressure_sensor = MockMPRLS(pressure)

    def open(self):
        self.state = "OPEN"

    def close(self):
        self.state = "CLOSED"

class MockMPRLS():
    """Mock MPRLS class to simulate pressure readings for unit testing."""

    def __init__(self, pressure):
        self._pressure_value = pressure

    def _get_pressure(self) -> float:
        """Simulate getting a single pressure reading."""
        return self._pressure_value

    def _get_triple_pressure(self) -> float:
        """Simulate getting a median of three pressure readings."""
        return self._pressure_value  # Mocking behavior; real one would compute a median

    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass

    # Define the properties to match the real class
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure of the MPRLS or -1 if it cannot be accessed"
    )

    triple_pressure = property(
        fget=_get_triple_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The 3-sample median pressure of the MPRLS or -1 if it cannot be accessed"
    )

@pytest.fixture
def mock_tank():
    """Fixture for a mocked tank."""
    return MockTank("Mock Tank")

def test_collection_initialization():
    """Test that a collection initializes correctly with expected attributes."""
    collection = Collection(
        num=1,
        up_start_time=40305, down_start_time=290000,
        bleed_duration=1, 
        up_driving_pressure=1270.44, down_driving_pressure=998.20,
        upwards_bleed=False
    )

    assert collection.num == "1"
    assert collection.up_start_time == 40305
    assert collection.down_start_time == 290000
    assert collection.bleed_duration == 1
    assert collection.up_driving_pressure == 1270.44
    assert collection.down_driving_pressure == 998.20
    assert collection.upwards_bleed is False
    assert collection.tank is None
    assert collection.pressure_sensor is None # Should be None when no tank is assigned
    assert collection.sampled is False
    assert collection.sample_upwards is True
    assert collection.sampled_count == 0

def test_collection_associate_tank(mock_tank):
    """Test associating a tank with a collection."""
    collection = Collection(
        num=2,
        up_start_time=70000, down_start_time=255000,
        bleed_duration=5,
        up_driving_pressure=753.43, down_driving_pressure=545.52,
        upwards_bleed=True
    )

    collection.associate_tank(mock_tank)

    assert collection.tank == mock_tank
    assert collection.pressure_sensor == mock_tank.pressure_sensor  # Ensure mprls is dynamically referenced

def test_collection_associate_tank_updates_properly(mock_tank):
    """Test re-associating a different tank and sensor with a collection."""
    collection = Collection(
        num=3,
        up_start_time=90000, down_start_time=230000,
        bleed_duration=36,
        up_driving_pressure=490.13, down_driving_pressure=329.96,
        upwards_bleed=True
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
        up_start_time=40305, down_start_time=290000,
        bleed_duration=1, 
        up_driving_pressure=1270.44, down_driving_pressure=998.20,
        upwards_bleed=False
    )
    
    collection2 = Collection(
        num=2,
        up_start_time=70000, down_start_time=255000,
        bleed_duration=5,
        up_driving_pressure=753.43, down_driving_pressure=545.52,
        upwards_bleed=True
    )
    
    collection3 = Collection(
        num=3,
        up_start_time=90000, down_start_time=230000,
        bleed_duration=36,
        up_driving_pressure=490.13, down_driving_pressure=329.96,
        upwards_bleed=True
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
        up_start_time=40305, down_start_time=290000,
        bleed_duration=1, 
        up_driving_pressure=1270.44, down_driving_pressure=998.20,
        upwards_bleed=False
    )
    
    collection2 = Collection(
        num=2,
        up_start_time=70000, down_start_time=255000,
        bleed_duration=5,
        up_driving_pressure=753.43, down_driving_pressure=545.52,
        upwards_bleed=True
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