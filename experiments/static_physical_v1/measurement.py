import math
import struct


def request(sequence):
    return bytes(1)+struct.pack('<I',12|((sequence%256)<<8)|(1<<17))+bytes(60)


def decode(raw,sequence,baseline=None):
    if len(raw)!=64:raise ValueError('ADC reply length')
    h,a=struct.unpack_from('<II',raw)
    if h&127!=65 or (h>>8)&255!=sequence%256 or a&32767!=1:
        raise ValueError('ADC reply type/id/attribute')
    v,i=struct.unpack_from('<ii',raw,16)
    v=v/1e6;i=i/1e6;consumed=-i
    if not 4.75<=v<=5.50:raise ValueError('run voltage envelope exceeded')
    if not 0<consumed<=3:raise ValueError('unexpected current sign or range')
    if baseline is not None and abs(v-baseline)>.30:raise ValueError('supply voltage shift')
    return {'volts':v,'signed_amps':i,'consumed_amps':consumed,'watts':v*consumed}


def integrate(samples):
    if len(samples)<2:raise ValueError('insufficient samples')
    energy=0
    for a,b in zip(samples,samples[1:]):
        dt=b['sample_monotonic']-a['sample_monotonic']
        if not 0<dt<=1.5:raise ValueError('invalid sample interval')
        if not all(math.isfinite(x['watts']) for x in (a,b)):raise ValueError('nonfinite power')
        energy+=(a['watts']+b['watts'])*.5*dt
    return energy,samples[-1]['sample_monotonic']-samples[0]['sample_monotonic']
