import pytest
import sys
sys.path.append('../')

import tempfile
import os
from pi.MPRLS import MPRLSFile

# Get file relative to the test file dir
PRESSURE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pressures.csv")

def test_mprlsfile_initialization():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\n20.3\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.file_path == temp_filename
    assert sensor.data == [10.5, 20.3, 30.7]
    os.remove(temp_filename)

def test_mprlsfile_empty_file():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []
    assert sensor._get_pressure() == -1
    assert sensor._get_triple_pressure() == -1
    os.remove(temp_filename)

def test_mprlsfile_get_pressure():
    sensor = MPRLSFile(PRESSURE_FILE)
    #assert isinstance(sensor._get_pressure(), float)
    with open(PRESSURE_FILE, "r") as f:
        data = [float(line.strip()) for line in f.readlines()]
    for value in data:
        assert sensor._get_pressure() == value

def test_mprlsfile_get_triple_pressure():
    sensor = MPRLSFile(PRESSURE_FILE)
    #assert isinstance(sensor._get_triple_pressure(), float)
    with open(PRESSURE_FILE, "r") as f:
        data = [float(line.strip()) for line in f.readlines()]
    for i in range(((len(data)-1) % 3) + 1):
        expected_values=[]
        for j in range(i*3, (i*3)+3):
            if j<len(data):
                expected_values+=[data[j]]
            else:
                expected_values+=[-1]
        assert sensor._get_triple_pressure() == sorted(expected_values)[1]  # Median calculation

def test_mprlsfile_corrupted_data():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\nINVALID\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []  # Should handle parsing failure gracefully
    assert sensor._get_pressure() == -1
    assert sensor._get_triple_pressure() == -1
    os.remove(temp_filename)
